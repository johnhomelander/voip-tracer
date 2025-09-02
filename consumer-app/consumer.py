# consumer-app/consumer.py
import json
import os
import tarfile
from pathlib import Path
import time
import geoip2.database
import requests
from elasticsearch import Elasticsearch
from kafka import KafkaConsumer
from kafka.errors import NoBrokersAvailable

# --- CONFIGURATION ---
BLACKLIST_URL = "https://raw.githubusercontent.com/firehol/blocklist-ipsets/master/firehol_level1.netset"
GEOIP_DB_PATH = Path("geoip_db/GeoLite2-City.mmdb")
MAXMIND_LICENSE_KEY = os.getenv("MAXMIND_LICENSE_KEY")
GEOIP_DOWNLOAD_URL = f"https://download.maxmind.com/app/geoip_download?edition_id=GeoLite2-City&license_key={MAXMIND_LICENSE_KEY}&suffix=tar.gz"
HIGH_RISK_COUNTRIES = {"Russia", "China", "Iran", "North Korea"}
KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:29092")
ELASTICSEARCH_URL = f"http://elastic:{os.getenv('ELASTIC_PASSWORD')}@elasticsearch:9200"

# --- SETUP FUNCTIONS ---
def setup_geoip_database():
    if GEOIP_DB_PATH.exists():
        print("GeoIP database found.", flush=True)
        return
    if not MAXMIND_LICENSE_KEY or MAXMIND_LICENSE_KEY == "YOUR_MAXMIND_LICENSE_KEY":
        print("WARNING: MaxMind license key not set in .env file. Skipping GeoIP setup.", flush=True)
        return
    
    print("Downloading GeoIP database...", flush=True)
    GEOIP_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    try:
        with requests.get(GEOIP_DOWNLOAD_URL, stream=True) as r:
            r.raise_for_status()
            with open("geoip.tar.gz", "wb") as f:
                f.write(r.content)
        
        with tarfile.open("geoip.tar.gz", "r:gz") as tar:
            for member in tar.getmembers():
                if member.name.endswith(".mmdb"):
                    member.name = os.path.basename(member.name)
                    tar.extract(member, path=GEOIP_DB_PATH.parent)
        os.remove("geoip.tar.gz")
        print("GeoIP setup complete.", flush=True)
    except requests.RequestException as e:
        print(f"Failed to download GeoIP database: {e}", flush=True)

def load_blacklist():
    print("Downloading IP blacklist...", flush=True)
    try:
        response = requests.get(BLACKLIST_URL)
        response.raise_for_status()
        ips = {line for line in response.text.splitlines() if not line.startswith("#") and line}
        print(f"Loaded {len(ips)} IPs into the blacklist.", flush=True)
        return ips
    except requests.RequestException:
        print("Failed to download blacklist.", flush=True)
        return set()

# --- MAIN EXECUTION ---
setup_geoip_database()
ip_blacklist = load_blacklist()
geoip_reader = None
if GEOIP_DB_PATH.exists():
    try:
        geoip_reader = geoip2.database.Reader(str(GEOIP_DB_PATH))
    except Exception as e:
        print(f"Could not load GeoIP database: {e}", flush=True)

# --- Wait for Kafka ---
print("Consumer service started. Attempting to connect to Kafka...", flush=True)
while True:
    try:
        consumer = KafkaConsumer(
            'voip_logs',
            bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
            value_deserializer=lambda m: json.loads(m.decode('utf-8', 'ignore')),
            group_id='voip_log_consumer_group',
            api_version=(0, 10, 2)
        )
        print("Successfully connected to Kafka. Waiting for messages...", flush=True)
        break
    except NoBrokersAvailable:
        print("Kafka not ready, waiting 5 seconds to retry...", flush=True)
        time.sleep(5)

es = Elasticsearch(ELASTICSEARCH_URL)
print("Connected to Elasticsearch. Starting message processing loop...", flush=True)

for message in consumer:
    log_data = message.value
    log_type = log_data.get("fields", {}).get("log_type")

    if log_type == "sip":
        # --- SIP LOG PROCESSING ---
        risk_score = 0
        tags = []
        src_ip = log_data.get("id.orig_h")
        dst_ip = log_data.get("id.resp_h")

        if src_ip in ip_blacklist or dst_ip in ip_blacklist:
            risk_score += 50
            tags.append("blacklist_match")

        if geoip_reader and src_ip:
            try:
                src_geo_info = geoip_reader.city(src_ip)
                log_data["src_geo"] = {"country": src_geo_info.country.name, "city": src_geo_info.city.name}
                if src_geo_info.country.name in HIGH_RISK_COUNTRIES:
                    risk_score += 20
                    tags.append("high_risk_country")
            except (geoip2.errors.AddressNotFoundError, TypeError):
                pass

        log_data["risk_score"] = risk_score
        if risk_score > 0:
            tags.append("alert")
        if tags:
            log_data["tags"] = tags

        try:
            es.index(index="voip_calls", document=log_data)
            print(f"Processed SIP log for Call-ID: {log_data.get('call_id')}", flush=True)
        except Exception as e:
            print(f"Failed to index SIP document: {e}", flush=True)

    elif log_type == "conn":
        # --- CONNECTION LOG PROCESSING ---
        try:
            es.index(index="conn_logs", document=log_data)
            print(f"Processed Connection log for flow: {log_data.get('uid')}", flush=True)
        except Exception as e:
            print(f"Failed to index CONN document: {e}", flush=True)
