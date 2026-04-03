import pandas as pd
from pymongo import MongoClient, UpdateOne
from datetime import datetime
import os
from dotenv import load_dotenv

load_dotenv()

MONGO_URL = os.getenv("MONGO_URL")
CSV_PATH = "ais_cleaned.csv"

def get_priority(v_type):
    """
    Priority Mapping:
    1: Fishing/Food
    2: Tankers
    3: Cargo/Commercial
    4: Military/Search
    5: Others/Pleasure
    """
    v_type = int(v_type) if v_type else 70
    if 30 <= v_type <= 35: return 1 # Fishing
    if 80 <= v_type <= 89: return 2 # Tankers
    if 70 <= v_type <= 79: return 3 # Cargo
    if 50 <= v_type <= 59: return 4 # Search/Special
    return 5

def ingest_data():
    client = MongoClient(MONGO_URL)
    db = client["port_simulation"]
    
    print(f"Reading {CSV_PATH}...")
    df = pd.read_csv(CSV_PATH)
    
    print("Preparing vessel metadata...")
    vessels_df = df.drop_duplicates(subset=['mmsi']).copy()
    vessels_data = []
    for _, row in vessels_df.iterrows():
        vessels_data.append({
            "mmsi": int(row['mmsi']),
            "vessel_name": str(row.get('vessel_name', 'Unknown')),
            "vessel_type": int(row.get('vessel_type', 70)),
            "priority": get_priority(row.get('vessel_type')),
            "imo": str(row.get('imo', 'Unknown')),
            "callsign": str(row.get('callsign', 'Unknown'))
        })

    print(f"Upserting {len(vessels_data)} vessels...")
    vessel_ops = [
        UpdateOne({"mmsi": v["mmsi"]}, {"$set": v}, upsert=True)
        for v in vessels_data
    ]
    db.vessels.bulk_write(vessel_ops)

    print("Preparing simulation events...")
    df['base_date_time'] = pd.to_datetime(df['base_date_time'])
    
    events_data = []
    for _, row in df.iterrows():
        events_data.append({
            "mmsi": int(row['mmsi']),
            "latitude": float(row['latitude']),
            "longitude": float(row['longitude']),
            "sog": float(row['sog']),
            "cog": float(row['cog']),
            "base_date_time": row['base_date_time'].to_pydatetime()
        })

    print(f"Inserting {len(events_data)} events into sim_events...")
    db.sim_events.delete_many({})
    db.sim_events.insert_many(events_data)
    2
    db.sim_events.create_index([("base_date_time", 1)])
    db.sim_events.create_index([("mmsi", 1)])

    print("Ingestion Complete!")

if __name__ == "__main__":
    if not MONGO_URL:
        print("Error: MONGO_URL not found in .env")
    else:
        ingest_data()
