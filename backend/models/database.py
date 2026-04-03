from pymongo import MongoClient
import os

# Connect locally
MONGO_URL = os.getenv("MONGODB_URI", "mongodb://localhost:27017/")
client = MongoClient(MONGO_URL)

DB_NAME = os.getenv("MONGODB_DB", "smart_docking_sim")
db = client[DB_NAME]

# Specific Time-series / state collections
ships_collection = db["simulated_ship_states"]
berths_collection = db["berths"]
events_collection = db["simulation_events"]
raw_data_collection = db["raw_ais_data"]

def setup_indexes():
    """Build time-based indexes for replayability and optimization."""
    ships_collection.create_index([("timestamp_ms", 1)])
    events_collection.create_index([("timestamp_ms", 1)])
    berths_collection.create_index([("berth_id", 1)], unique=True)
    
if __name__ == "__main__":
    setup_indexes()
    print("Database collections and indexes successfully initialized.")
