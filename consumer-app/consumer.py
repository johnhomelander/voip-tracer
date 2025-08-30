import json
import os
import tarfile
from pathlib import Path
import geoip2.database
import requests
from elasticsearch import Elasticsearch
from kafka import KafkaConsumer

# --- CONFIGURATION ---
BLACKLIST_URL = "https://raw.githubusercontent.com/firehol/blocklist-ipsets/master/firehol_level1.netset"
GEOIP_DB_PATH = Path("geoip_db/GeoLite2-City.mmdb")
MAXMIND_LICENSE_KEY = os.getenv("MAXMIND_LICENSE_KEY", "YOUR_MAXMIND_LICENSE_KEY")
GEOIP_DOWNLOAD_URL = f"https://download.maxmind.com/app/geoip_download?edition_id=GeoLite2-City&license_key={MAXMIND_LICENSE_KEY}&suffix=tar.gz"
HIGH_RISK_COUNTRIES = {"Russia", "China", "Iran", "North Korea"}

# --- SETUP FUNCTIONS (Same as before) ---
def setup_geoip_database():
    if GEOIP_DB_PATH.exists(): return
    if not MAXMIND_LICENSE_KEY or MAXMIND_LICENSE_KEY == "YOUR_MAXMIND_LICENSE_KEY":
        print("WARNING: MaxMind license key not set. Skipping GeoIP setup.")
        return
    print("Downloading GeoIP database...")
    GEOIP_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with requests.get(GEOIP_DOWNLOAD_URL, stream=True) as r:
        r.raise_for_status()
        with open("geoip.tar.gz", "wb") as f: f.write(r.content)
    with tarfile.open("geoip.tar.gz", "r:gz") as tar:
        for member in tar.getmembers():
            if member.name.endswith(".mmdb"):
                member.name = os.path.basename(member.name)
                tar.extract(member, path=GEOIP_DB_PATH.parent)
    os.remove("geoip.tar.gz")
    print("GeoIP setup complete.")

def load_blacklist():
    print("Downloading IP blacklist...")
    try:
        response = requests.get(BLACKLIST_URL)
        response.raise_for_status()
        ips = {line for line in response.text.splitlines() if not line.startswith("#") and line}
        print(f"Loaded {len(ips)} IPs into the blacklist.")
        return ips
    except requests.RequestException: return set()

# --- MAIN EXECUTION ---
setup_geoip_database()
ip_blacklist = load_blacklist()
geoip_reader = geoip2.database.Reader(str(GEOIP_DB_PATH)) if GEOIP_DB_PATH.exists() else None

es = Elasticsearch(os.getenv("ELASTICSEARCH_HOST", "http://localhost:9200"))
consumer = KafkaConsumer('voip_logs', bootstrap_servers=os.getenv("KAFKA_BOOTSTRAP_SERVERS", 'kafka:29092'),
                         value_deserializer=lambda m: json.loads(m.decode('utf-8', 'ignore')))

print("Starting the enriched consumer with scoring logic...")
for message in consumer:
    log_data = message.value
    risk_score = 0
    tags = []

    src_ip = log_data.get("id.orig_h")
    dst_ip = log_data.get("id.resp_h")

    # 1. Threat Intel Check
    if src_ip in ip_blacklist or dst_ip in ip_blacklist:
        risk_score += 50
        tags.append("blacklist_match")

    # 2. GeoIP Enrichment & Scoring
    if geoip_reader:
        try:
            src_geo_info = geoip_reader.city(src_ip)
            log_data["src_geo"] = {"country": src_geo_info.country.name, "city": src_geo_info.city.name}
            if src_geo_info.country.name in HIGH_RISK_COUNTRIES:
                risk_score += 20
                tags.append("high_risk_country")
        except geoip2.errors.AddressNotFoundError: pass

        try:
            dst_geo_info = geoip_reader.city(dst_ip)
            log_data["dst_geo"] = {"country": dst_geo_info.country.name, "city": dst_geo_info.city.name}
        except geoip2.errors.AddressNotFoundError: pass

    # 3. Finalize and Index
    log_data["risk_score"] = risk_score
    if risk_score > 0: tags.append("alert")
    if tags: log_data["tags"] = tags

    es.index(index="voip_calls", id=log_data.get("uid"), document=log_data)
    print(f"Processed Call-ID: {log_data.get('call_id')} | Risk Score: {risk_score}")
