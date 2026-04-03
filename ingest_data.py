import pandas as pd
import numpy as np
from pymongo import MongoClient
from dotenv import load_dotenv
import os
import random

load_dotenv()

def map_vessel_type(vt):
    """
    Map AIS numeric codes (70-89, etc) to User Categories.
    """
    if 80 <= vt <= 89: return "Tanker"
    if 60 <= vt <= 69: return "Roll-On"
    if 71 <= vt <= 72: return "Bulk Carrier"
    if 70 == vt: return "Container"
    
    if 73 <= vt <= 79:
        return "Food Ship" if random.random() < 0.3 else "Container"
    
    return "Other"

def ingest_and_configure():
    mongo_url = os.getenv("MONGO_URL")
    client = MongoClient(mongo_url)
    db = client["port_simulation"]
    
    vessels_col = db["vessels"]
    events_col = db["sim_events"]
    risks_col = db["risks"]
    
    vessels_col.delete_many({})
    events_col.delete_many({})
    risks_col.delete_many({})
    
    print("Loading cleaned AIS data...")
    df = pd.read_csv("ais_cleaned.csv", nrows=100000) 
    
    print("Enriching data with categories and priorities...")
    df['category'] = df['vessel_type'].apply(map_vessel_type)
    
    priority_map = {
        "Food Ship": 1,
        "Tanker": 2,
        "Roll-On": 3,
        "Container": 4,
        "Bulk Carrier": 5,
        "Other": 6
    }
    df['priority'] = df['category'].map(priority_map)
    
    print("Syncing vessel metadata...")
    unique_vessels = df.drop_duplicates(subset=['mmsi'])
    vessel_docs = unique_vessels[['mmsi', 'vessel_name', 'category', 'priority', 'length', 'width']].to_dict('records')
    vessels_col.insert_many(vessel_docs)
    
    print("Configuring simulation events...")
    df = df.sort_values(by='base_date_time')
    
    event_docs = df[['mmsi', 'base_date_time', 'longitude', 'latitude', 'sog', 'cog']].to_dict('records')
    events_col.insert_many(event_docs)
    
    print("Creating indices for time-series playback...")
    events_col.create_index([("base_date_time", 1)])
    events_col.create_index([("mmsi", 1)])
    
    print("Injecting synthetic risks (Weather, War Zones)...")
    risks = [
        {"name": "Storm Zone A", "lat_range": [26.0, 28.0], "lon_range": [-85.0, -80.0], "risk_type": "Weather", "delay_factor": 0.5},
        {"name": "Restricted Zone B", "lat_range": [18.0, 20.0], "lon_range": [-70.0, -65.0], "risk_type": "Geopolitical", "delay_factor": 0.2}
    ]
    risks_col.insert_many(risks)
    
    print(f"Ingestion complete. Vessels: {len(vessel_docs)}, Events: {len(event_docs)}, Risks: {len(risks)}")

if __name__ == "__main__":
    ingest_and_configure()
