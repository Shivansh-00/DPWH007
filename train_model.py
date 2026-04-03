import pandas as pd
import numpy as np
import joblib
from sklearn.ensemble import RandomForestRegressor
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split
import math

PORT_LAT = 29.98
PORT_LON = -90.0

def haversine(lat1, lon1, lat2, lon2):
    R = 6371 
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) * math.sin(dlat / 2) +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
         math.sin(dlon / 2) * math.sin(dlon / 2))
    c = 2 * math.asin(math.sqrt(a))
    return R * c

def train_pdds_ai():
    print("Loading data for AI training...")
    df = pd.read_csv("ais_cleaned.csv", nrows=200000)
    
    print("Calculating distances and engineering features...")
    df['dist_to_port'] = df.apply(lambda r: haversine(r['latitude'], r['longitude'], PORT_LAT, PORT_LON), axis=1)
    
    noise = np.random.normal(0, 5, len(df))
    df['arrival_time_label'] = (df['dist_to_port'] / (df['sog'] + 0.1) * 60) + noise
    
    X = df[['sog', 'cog', 'dist_to_port', 'vessel_type']].fillna(0)
    y = df['arrival_time_label'].fillna(0)
    
    print("Training Random Forest Regressor...")
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    
    model = RandomForestRegressor(n_estimators=50, max_depth=10, random_state=42)
    model.fit(X_train_scaled, y_train)
    
    score = model.score(scaler.transform(X_test), y_test)
    print(f"Model Training Complete. R² Score: {score:.4f}")
    
    print("Exporting model artifacts...")
    joblib.dump(model, "pdds_model.joblib")
    joblib.dump(scaler, "pdds_scaler.joblib")
    
if __name__ == "__main__":
    train_pdds_ai()
