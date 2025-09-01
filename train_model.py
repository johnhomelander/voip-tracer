# train_model.py
import pandas as pd
import joblib
from elasticsearch import Elasticsearch
import os

print("Starting model training...")
es = Elasticsearch(os.getenv("ELASTICSEARCH_URL"))
model_filename = 'isolation_forest.joblib'

try:
    # Query Elasticsearch for all available call data to use for training
    response = es.search(index="voip_calls", body={"query": {"match_all": {}}}, size=10000)
    hits = [hit['_source'] for hit in response['hits']['hits']]
    if not hits:
        print("No data in Elasticsearch to train on. Please upload a PCAP first.")
        exit()

    df = pd.DataFrame(hits)
    print(f"Loaded {len(df)} records for training.")

    # --- Feature Engineering ---
    df['duration'] = pd.to_numeric(df.get('duration'), errors='coerce').fillna(0)
    features = df.groupby('id.orig_h').agg(
        call_frequency=('ts', 'count'),
        avg_duration=('duration', 'mean')
    ).reset_index()

    X = features[['call_frequency', 'avg_duration']]

    # --- Model Training ---
    model = IsolationForest(n_estimators=100, contamination='auto', random_state=42)
    model.fit(X)

    joblib.dump(model, model_filename)
    print(f"\nModel training complete. Model saved as '{model_filename}'")

except Exception as e:
    print(f"An error occurred: {e}")
