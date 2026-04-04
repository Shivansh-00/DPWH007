import os
import sys

def seed_if_empty():
    """Seed only when database is truly empty and CSV source exists."""
    from backend.models.database import db

    # If the user already has any data in this DB, do not run preload.
    has_any_data = False
    for collection_name in db.list_collection_names():
        if db[collection_name].estimated_document_count() > 0:
            has_any_data = True
            break

    if has_any_data:
        print("[Seed] Database already has data. Skipping preload.")
        return

    csv_path = os.path.normpath(
        os.path.join(os.path.dirname(__file__), "..", "..", "data", "ais_raw.csv")
    )
    if not os.path.exists(csv_path):
        print(f"[Seed] CSV not found at {csv_path}. Skipping preload.")
        return

    print("[Seed] Database is empty. Initiating data preload...")
    try:
        from data_pipeline.data_loader import run_pipeline
        run_pipeline()
        print("[Seed] Data preload complete.")
    except Exception as e:
        print(f"[Seed] Failed to preload data: {e}", file=sys.stderr)

if __name__ == "__main__":
    seed_if_empty()
