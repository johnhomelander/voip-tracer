# analysis-service/analyzer.py (Final, Complete & Corrected Version)
import os
import time
import pandas as pd
import joblib
from elasticsearch import Elasticsearch
from elasticsearch.helpers import bulk

print("Starting Analysis Service...")

# --- SETUP ---
try:
    model = joblib.load('isolation_forest.joblib')
    print("Successfully loaded Isolation Forest model.")
except FileNotFoundError:
    print("ERROR: 'isolation_forest.joblib' not found. Please run the training script first.")
    exit()

es = Elasticsearch(os.getenv("ELASTICSEARCH_URL"))
print("Connected to Elasticsearch.")

# --- MAIN ANALYSIS LOOP ---
while True:
    print("Running analysis cycle...")
    try:
        # 1. QUERY DATA: Fetch recent SIP and Connection logs
        time_filter = {"range": {"ts": {"gte": "now-15m/m", "lt": "now/m"}}}
        
        sip_response = es.search(index="voip_calls", query=time_filter, size=5000)
        conn_response = es.search(index="conn_logs", query=time_filter, size=10000)

        sip_hits = sip_response['hits']['hits']
        conn_hits = conn_response['hits']['hits']

        if not sip_hits:
            print("No new SIP data to analyze.")
            time.sleep(60) # Sleep for 1 minute if no data
            continue

        # 2. CORRELATE: Link SIP calls with their media flows
        sip_df = pd.DataFrame([h['_source'] for h in sip_hits])
        sip_df['_id'] = [h['_id'] for h in sip_hits]
        sip_df['ts'] = pd.to_datetime(sip_df['ts'], unit='s')
        
        if conn_hits:
            conn_df = pd.DataFrame([h['_source'] for h in conn_hits])
            conn_df['ts'] = pd.to_datetime(conn_df['ts'], unit='s')
            
            # Sort for merging
            sip_df = sip_df.sort_values('ts')
            conn_df = conn_df.sort_values('ts')
            
            # Correlate by finding the closest connection log after a SIP log starts
            merged_df = pd.merge_asof(
                sip_df,
                conn_df,
                on='ts',
                by=['id.orig_h', 'id.resp_h'],
                direction='forward',
                tolerance=pd.Timedelta('5s')
            )
        else:
            merged_df = sip_df # If no conn logs, just use sip data

        # 3. FEATURE ENGINEERING: Calculate features from your report
        # We use .get() to safely access keys that might not exist
        merged_df['media_flow_duration'] = pd.to_numeric(merged_df.get('duration_y'), errors='coerce').fillna(0)
        merged_df['media_byte_count'] = merged_df.get('orig_bytes', 0) + merged_df.get('resp_bytes', 0)
        
        # Aggregate features by source IP
        features = merged_df.groupby('id.orig_h').agg(
            call_frequency=('ts', 'count'),
            avg_duration=('media_flow_duration', 'mean'),
            total_bytes=('media_byte_count', 'sum')
        ).reset_index()

        # 4. ML PREDICTION: Find anomalies
        X = features[['call_frequency', 'avg_duration', 'total_bytes']].fillna(0)
        if not X.empty:
            predictions = model.predict(X)
            features['anomaly'] = predictions
            anomalous_ips = features[features['anomaly'] == -1]['id.orig_h'].tolist()

            if anomalous_ips:
                print(f"Found anomalous IPs via ML model: {anomalous_ips}")
                
                # 5. UPDATE & SCORE: Update records in Elasticsearch
                actions = []
                for _, row in merged_df[merged_df['id.orig_h'].isin(anomalous_ips)].iterrows():
                    existing_tags = row.get("tags", [])
                    if "ml_anomaly" not in existing_tags: # Avoid adding the tag multiple times
                        actions.append({
                            "_op_type": "update",
                            "_index": "voip_calls",
                            "_id": row["_id"],
                            "doc": {
                                "tags": existing_tags + ["ml_anomaly"],
                                "risk_score": row.get("risk_score", 0) + 25
                            }
                        })
                
                if actions:
                    bulk(es, actions)
                    print(f"Updated {len(actions)} records with ML anomaly tag.")
            else:
                print("No ML anomalies detected in this cycle.")

    except Exception as e:
        print(f"An error occurred during analysis: {e}")

    print("Analysis cycle complete. Sleeping for 5 minutes...")
    time.sleep(300)
