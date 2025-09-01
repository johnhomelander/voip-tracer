import os
import time
import pandas as pd
import joblib
from elasticsearch import Elasticsearch
from elasticsearch.helpers import bulk

print("Starting Analysis Service...")
model = joblib.load('isolation_forest.joblib')
es = Elasticsearch(f"http://elastic:{os.getenv('ELASTIC_PASSWORD')}@elasticsearch:9200")

while True:
    print("Running anomaly detection cycle...")
    try:
        query = {"query": {"range": {"ts": {"gte": "now-5m/m", "lt": "now/m" }}}}
        response = es.search(index="voip_calls", body=query, size=10000)

        hits = response['hits']['hits']
        if not hits:
            print("No new call data to analyze.")
        else:
            df = pd.DataFrame([h['_source'] for h in hits])
            df['_id'] = [h['_id'] for h in hits] # Keep track of document IDs

            df['duration'] = pd.to_numeric(df.get('duration'), errors='coerce').fillna(0)
            features = df.groupby('id.orig_h').agg(
                call_frequency=('ts', 'count'),
                avg_duration=('duration', 'mean')
            ).reset_index()

            X = features[['call_frequency', 'avg_duration']]
            predictions = model.predict(X)
            features['anomaly'] = predictions

            anomalous_ips = features[features['anomaly'] == -1]['id.orig_h'].tolist()

            if anomalous_ips:
                print(f"Found anomalous IPs: {anomalous_ips}")

                # Prepare bulk update for anomalous records
                actions = []
                for _, row in df[df['id.orig_h'].isin(anomalous_ips)].iterrows():
                    actions.append({
                        "_op_type": "update",
                        "_index": "voip_calls",
                        "_id": row["_id"],
                        "doc": {
                            "tags": row.get("tags", []) + ["ml_anomaly"],
                            "risk_score": row.get("risk_score", 0) + 25
                        }
                    })

                if actions:
                    bulk(es, actions)
                    print(f"Updated {len(actions)} records with ML anomaly tag.")
            else:
                print("No anomalies detected.")

    except Exception as e:
        print(f"An error occurred during analysis: {e}")

    print("Sleeping for 5 minutes...")
    time.sleep(300)
