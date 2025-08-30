# main.py
from fastapi import FastAPI, HTTPException
from fastapi_users import FastAPIUsers
from elasticsearch import Elasticsearch

import os
from contextlib import asynccontextmanager

from auth import auth_backend
from db import User, create_db_and_tables, get_user_db
from schemas import UserCreate, UserRead, UserUpdate

@asynccontextmanager
async def lifespan(app: FastAPI):
    await create_db_and_tables()
    yield

# Initialize the FastAPI app
app = FastAPI(title="VoIP Tracer API")

# Connect to Elasticsearch using the environment variable from docker-compose
try:
    es_host = os.getenv("ELASTICSEARCH_HOST", "http://localhost:9200")
    es = Elasticsearch(es_host)
    print(f"Successfully connected to Elasticsearch at {es_host}")
except Exception as e:
    print(f"Could not connect to Elasticsearch: {e}")
    es = None

@app.get("/")
def read_root():
    return {"status": "VoIP Tracer API is running"}

@app.get("/calls")
async def get_recent_calls(limit: int = 100):
    """
    Fetches the most recent SIP events from Elasticsearch.
    """
    if not es:
        raise HTTPException(status_code=500, detail="Elasticsearch connection not available")

    # A simple Elasticsearch query to get the latest 'limit' documents
    # sorted by timestamp in descending order.
    query = {
        "sort": [{"ts": {"order": "desc"}}],
        "size": limit
    }

    try:
        response = es.search(index="voip_calls", body=query)
        # Extract the actual documents from the response
        hits = [hit['_source'] for hit in response['hits']['hits']]
        return {"calls": hits}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error querying Elasticsearch: {e}")

@app.get("/search")
async def search_calls(ip: str = None, call_id: str = None):
    """
    Searches for calls involving a specific IP or with a specific Call-ID.
    """
    if not es:
        raise HTTPException(status_code=500, detail="Elasticsearch connection not available")
    if not ip and not call_id:
        raise HTTPException(status_code=400, detail="Please provide an 'ip' or 'call_id' query parameter.")

    # Build an Elasticsearch "bool" query to match multiple conditions
    query = {
        "query": {
            "bool": {
                "should": [
                    {"term": {"id.orig_h": ip}},
                    {"term": {"id.resp_h": ip}},
                    {"match": {"call_id.keyword": call_id}} # Use .keyword for exact matches
                ],
                "minimum_should_match": 1
            }
        }
    }
    
    try:
        response = es.search(index="voip_calls", body=query)
        hits = [hit['_source'] for hit in response['hits']['hits']]
        return {"results": hits}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error querying Elasticsearch: {e}")
