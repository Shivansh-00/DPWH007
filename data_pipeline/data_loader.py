"""
Standalone Data Loader for AIS Raw Dataset (722MB)
Run this ONCE to preprocess the dataset and load it into MongoDB.
"""

import os
import csv
from datetime import datetime
import pymongo
from dotenv import load_dotenv

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
CLIENT = pymongo.MongoClient(MONGO_URI)
DB = CLIENT["smart_docking_sim"]
COLLECTION = DB["raw_ais_data"]

CSV_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'data', 'ais_raw.csv')

# Maps numeric vessel types to our String enums loosely
VESSEL_TYPE_MAP = {
    "70": "Cargo",
    "71": "Cargo",
    "72": "Cargo",
    "73": "Cargo",
    "74": "Cargo",
    "80": "Tanker",
    "81": "Tanker",
    "82": "Tanker",
    "83": "Tanker",
    "84": "Tanker",
}

def clean_value(val, cast_type=float, default=0.0):
    if not val:
        return default
    try:
        return cast_type(val)
    except:
        return default

def process_batch(batch):
    """Clean and filter a batch of rows before insertion."""
    cleaned = []
    
    # We want to downsample per ship slightly, so we track latest timestamps per mmsi
    # Though in a chunked script that's hard across chunks, so we rely on time parsing
    for row in batch:
        mmsi = row.get("mmsi")
        lat = clean_value(row.get("latitude"))
        lon = clean_value(row.get("longitude"))
        sog = clean_value(row.get("sog"))
        
        # Filter invalid
        if not mmsi or lat == 0.0 or lon == 0.0:
            continue
            
        # Optional: Skip zero speed unless intentional? 
        # For AIS, lots of 0.0 means docked. We'll load them but maybe filter in scenario gen.
            
        dt_str = row.get("base_date_time", "")
        # AIS format '2024-01-10 00:00:00'
        try:
            timestamp = datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S")
        except:
            continue
            
        # Map vessel type
        v_type_raw = row.get("vessel_type", "")
        ship_type = "Container" # Default fallback
        if v_type_raw in VESSEL_TYPE_MAP:
            ship_type = VESSEL_TYPE_MAP[v_type_raw]
            if ship_type == "Cargo":
                ship_type = "Bulk Carrier" # Map to our enum
                
        doc = {
            "ship_id": mmsi,
            "timestamp": timestamp,
            "lat": lat,
            "lon": lon,
            "speed": sog,
            "heading": clean_value(row.get("heading")),
            "ship_type": ship_type,
            "vessel_name": row.get("vessel_name", f"Ship {mmsi}"),
            "state": "APPROACHING" # Default
        }
        cleaned.append(doc)
    return cleaned


def run_pipeline(batch_sizes=20000, max_rows=None):
    print("Initialize MongoDB Collection and Indices...")
    # Clean old
    COLLECTION.drop()
    
    # Create Indices
    COLLECTION.create_index([("ship_id", pymongo.ASCENDING)])
    COLLECTION.create_index([("timestamp", pymongo.ASCENDING)])
    COLLECTION.create_index([("ship_id", pymongo.ASCENDING), ("timestamp", pymongo.ASCENDING)])
    print("Indices created.")

    print(f"Reading from {CSV_PATH}...")
    
    batch = []
    total_processed = 0
    total_inserted = 0
    
    with open(CSV_PATH, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        
        # Simple local dictionary to downsample: only keep 1 record per ship per minute
        last_seen = {}
        
        for i, row in enumerate(reader):
            if max_rows and i >= max_rows:
                break
                
            mmsi = row.get("mmsi")
            dt_str = row.get("base_date_time", "")
            
            # Simple downsampling based on minute string matching:
            # We ignore multiple records for the same ship in the same minute
            # "2024-01-10 00:00:00" -> minute key "2024-01-10 00:00"
            minute_key = f"{mmsi}_{dt_str[:16]}" 
            
            if last_seen.get(minute_key):
                continue
                
            last_seen[minute_key] = True
            
            batch.append(row)
            total_processed += 1
            
            if len(batch) >= batch_sizes:
                cleaned = process_batch(batch)
                if cleaned:
                    COLLECTION.insert_many(cleaned)
                    total_inserted += len(cleaned)
                batch = []
                print(f"Processed: {total_processed} | Inserted: {total_inserted} ...")
                
                # Cleanup huge dict
                if len(last_seen) > 500000:
                    last_seen.clear()
                    
    # Insert remainder
    if batch:
        cleaned = process_batch(batch)
        if cleaned:
            COLLECTION.insert_many(cleaned)
            total_inserted += len(cleaned)

    print("=======================================")
    print(f"Pipeline Complete!")
    print(f"Raw rows read (downsampled): {total_processed}")
    print(f"Total inserted into MongoDB: {total_inserted}")
    print("=======================================")

if __name__ == "__main__":
    # Feel free to set max_rows=100000 for quick testing, or None for full
    run_pipeline(max_rows=150000) 
