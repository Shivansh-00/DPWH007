import os
import sys

def seed_if_empty():
    """Check if the DB has AIS data. If not, trigger the data_loader pipeline."""
    from backend.models.database import raw_data_collection
    
    count = raw_data_collection.estimated_document_count()
    if count > 0:
        print(f"[Seed] Database already contains {count} records. Skipping seed.")
        return
        
    print("[Seed] Database is empty! Initiating data preload...")
    try:
        from data_pipeline.data_loader import run_pipeline
        run_pipeline()
        print("[Seed] Data preload complete.")
    except Exception as e:
        print(f"[Seed] Failed to preload data: {e}", file=sys.stderr)

if __name__ == "__main__":
    seed_if_empty()
