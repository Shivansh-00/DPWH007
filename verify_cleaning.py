import pandas as pd
import numpy as np

def verify_cleaning(file_path):
    print(f"Verifying cleaned data from {file_path}...")
    df = pd.read_csv(file_path)
    
    duplicates = df.duplicated().sum()
    print(f"Duplicates: {duplicates} (Expected: 0)")
    
    lat_in_range = ((df['latitude'] >= -90) & (df['latitude'] <= 90)).all()
    lon_in_range = ((df['longitude'] >= -180) & (df['longitude'] <= 180)).all()
    print(f"Latitude in range: {lat_in_range} (Expected: True)")
    print(f"Longitude in range: {lon_in_range} (Expected: True)")
    
    has_511 = (df['heading'] == 511.0).sum()
    has_3600 = (df['cog'] >= 360.0).sum()
    print(f"Heading with 511.0: {has_511} (Expected: 0)")
    print(f"COG >= 360.0: {has_3600} (Expected: 0)")
    
    print("\n--- Current Missing Values ---")
    print(df.isnull().sum())
    
    static_cols = ['vessel_name', 'vessel_type', 'imo', 'call_sign', 'length', 'width']
    print("\n--- Remaining Missing Static Info (per MMSI) ---")
    mmsi_missing = df.groupby('mmsi')[static_cols].apply(lambda x: x.isnull().all()).sum()
    print(mmsi_missing)
    print("(Note: These are MMSIs that have NO metadata at all, which backfilling can't fix)")

if __name__ == "__main__":
    verify_cleaning("ais_cleaned.csv")
