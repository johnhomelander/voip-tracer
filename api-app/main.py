# api-app/main.py (Complete with /search endpoint)
import os
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi_users import FastAPIUsers
from elasticsearch import Elasticsearch

from auth import auth_backend, get_user_manager
from db import User, create_db_and_tables, get_user_db
from schemas import UserCreate, UserRead, UserUpdate

import subprocess
from fastapi import UploadFile, File
from kafka import KafkaProducer
import json

ROOT_PATH = os.getenv("ROOT_PATH", "")
KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:29092")

@asynccontextmanager
async def lifespan(app: FastAPI):
    await create_db_and_tables()
    yield

app = FastAPI(title="VoIP Tracer API", lifespan=lifespan, root_path=ROOT_PATH,docs_url=None,redoc_url=None)

# This list defines which origins are allowed to connect.
origins = [
    "http://localhost:3000",
    "https://voiptracer.pranavsahni.tech",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"], # Allow all methods
    allow_headers=["*"], # Allow all headers
)

es = Elasticsearch(os.getenv("ELASTICSEARCH_URL"))

fastapi_users = FastAPIUsers[User, int](get_user_manager, [auth_backend])
current_active_user = fastapi_users.current_user(active=True)

app.include_router(fastapi_users.get_auth_router(auth_backend), prefix="/auth/jwt", tags=["auth"])
#app.include_router(fastapi_users.get_register_router(UserRead, UserCreate), prefix="/auth", tags=["auth"])
app.include_router(fastapi_users.get_users_router(UserRead, UserUpdate), prefix="/users", tags=["users"])

@app.get("/calls", tags=["VoIP Data"])
async def get_recent_calls(limit: int = 100, user: User = Depends(current_active_user)):
    query = {"sort": [{"ts": {"order": "desc"}}], "size": limit}
    try:
        response = es.search(index="voip_calls", body=query)
        return {"calls": [hit['_source'] for hit in response['hits']['hits']]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/search", tags=["VoIP Data"])
async def search_calls(ip: str, user: User = Depends(current_active_user)):
    """
    Searches for calls involving a specific IP address.
    """
    query = {
        "query": {
            "bool": {
                "should": [
                    {"term": {"id.orig_h.keyword": ip}},
                    {"term": {"id.resp_h.keyword": ip}}
                ],
                "minimum_should_match": 1
            }
        },
        "sort": [{"ts": {"order": "desc"}}]
    }
    try:
        response = es.search(index="voip_calls", body=query)
        return {"results": [hit['_source'] for hit in response['hits']['hits']]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/pcap/upload", tags=["PCAP Analysis"])
async def upload_pcap(
    file: UploadFile = File(...),
    user: User = Depends(current_active_user)
):
    pcap_path = f"/pcap_storage/{file.filename}"

    # Save the uploaded file to the shared volume
    with open(pcap_path, "wb") as buffer:
        buffer.write(await file.read())

    # Send a job message to the 'pcap_jobs' topic with the filename
    try:
        producer = KafkaProducer(
            bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
            value_serializer=lambda v: json.dumps(v).encode('utf-8')
        )
        producer.send('pcap_jobs', {'filename': file.filename})
        producer.flush()
        producer.close()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Could not send job to Kafka: {e}")

    return {"status": "success", "message": f"File '{file.filename}' uploaded and queued for analysis."}

@app.get("/stats/risk_distribution", tags=["Stats"])
async def get_risk_distribution(user: User = Depends(current_active_user)):
    query = {"size":0,"aggs":{"risk_scores":{"range":{"field":"risk_score","ranges":[{"to":1,"key":"Low"},{"from":1,"to":49,"key":"Medium"},{"from":50,"key":"High"}]}}}}
    try:
        response = es.search(index="voip_calls", body=query)
        buckets = response['aggregations']['risk_scores']['buckets']
        return {"labels": [b['key'] for b in buckets], "data": [b['doc_count'] for b in buckets]}
    except Exception: return {"labels": [], "data": []}

@app.get("/stats/timeline", tags=["Stats"])
async def get_timeline(user: User = Depends(current_active_user)):
    query = {"size":0,"aggs":{"calls_over_time":{"date_histogram":{"field":"ts","calendar_interval":"1h","time_zone":"UTC"}}}}
    try:
        response = es.search(index="voip_calls", body=query)
        buckets = response['aggregations']['calls_over_time']['buckets']
        return {"labels": [b['key_as_string'] for b in buckets], "data": [b['doc_count'] for b in buckets]}
    except Exception: return {"labels": [], "data": []}
