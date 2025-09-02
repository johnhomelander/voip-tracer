# train_model.py
import pandas as pd
import joblib
from elasticsearch import Elasticsearch
import os
from sklearn.ensemble import IsolationForest

print("Starting model training...")
es = Elasticsearch(f"http://elastic:{os.getenv('ELASTIC_PASSWORD')}@elasticsearch:9200")
model_filename = 'isolation_forest.joblib'

try:
    # Use the modern 'query' parameter to fix the DeprecationWarning
    response = es.search(index="voip_calls", query={"match_all": {}}, size=10000)

    hits = [hit['_source'] for hit in response['hits']['hits']]
    if not hits:
        print("No data in Elasticsearch to train on. Please upload a PCAP first.")
        exit()

    df = pd.DataFrame(hits)
    print(f"Loaded {len(df)} records for training.")

    # --- Feature Engineering (More Robust) ---

    # Check if the 'duration' column exists. If not, create it with zeros.
    if 'duration' not in df.columns:
        df['duration'] = 0

    # Now, we can safely process the column, knowing it exists.
    df['duration'] = pd.to_numeric(df['duration'], errors='coerce').fillna(0)

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
