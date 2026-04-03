import pandas as pd
import numpy as np
import time

def clean_ais_data(input_file, output_file):
    start_time = time.time()
    print(f"Loading data from {input_file}...")
    
    dtypes = {
        'mmsi': 'int32',
        'longitude': 'float32',
        'latitude': 'float32',
        'sog': 'float32',
        'cog': 'float32',
        'heading': 'float32',
        'vessel_name': 'category',
        'imo': 'str',
        'call_sign': 'str',
        'vessel_type': 'category',
        'status': 'category',
        'length': 'float32',
        'width': 'float32',
        'draft': 'float32',
        'cargo': 'float32',
        'transceiver': 'category'
    }
    
    df = pd.read_csv(input_file, dtype=dtypes, parse_dates=['base_date_time'])
    print(f"Loaded {len(df)} rows. Memory usage: {df.memory_usage(deep=True).sum() / 1024**2:.2f} MB")
    
    print("Deduplicating...")
    initial_len = len(df)
    df.drop_duplicates(inplace=True)
    print(f"Removed {initial_len - len(df)} duplicate rows.")
    
    print("Filtering invalid coordinates...")
    df = df[(df['latitude'] >= -90) & (df['latitude'] <= 90)]
    df = df[(df['longitude'] >= -180) & (df['longitude'] <= 180)]
    print(f"Remaining rows after coordinate filtering: {len(df)}")
    
    print("Converting special missing codes (511, 3600) to NaN...")
    df.loc[df['heading'] == 511.0, 'heading'] = np.nan
    df.loc[df['cog'] >= 360.0, 'cog'] = np.nan
    
    print("Backfilling static metadata by MMSI...")
    static_cols = ['vessel_name', 'vessel_type', 'imo', 'call_sign', 'length', 'width']
    
    for col in static_cols:
        print(f"  Backfilling {col}...")
        df[col] = df.groupby('mmsi')[col].transform(lambda x: x.ffill().bfill())
        
    print("Cleaning speed (SOG)...")
    df.loc[df['sog'] < 0, 'sog'] = np.nan
    df.loc[df['sog'] > 102.3, 'sog'] = np.nan 
    
    print("Handling status and final NaNs...")
    df['status'] = df.groupby('mmsi')['status'].transform(lambda x: x.ffill().bfill())
    
    print(f"Saving cleaned data to {output_file}...")
    df.to_csv(output_file, index=False)
    
    end_time = time.time()
    print(f"Data cleaning complete in {end_time - start_time:.2f} seconds.")
    print(f"Final Row Count: {len(df)}")

if __name__ == "__main__":
    clean_ais_data("ais_raw.csv", "ais_cleaned.csv")
