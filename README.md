# TEAM: DPWH007
# Port Docking Decision System (PDDS) Command Center

## Project Overview
The Port Docking Decision System (PDDS) is a high-fidelity maritime simulation and decision-support platform. It utilizes historical AIS (Automatic Identification System) data to recreate port operations, simulate environmental stressors, and provide AI-driven predictive insights into vessel arrival times. The system is designed to optimize berth occupancy and prioritize vessel entry based on cargo priority and operational risk.

## Technical Architecture

### 1. Data Infrastructure
- **Historical Playback**: The system processes and replays real-world AIS datasets from January 2024. Data is stored in MongoDB as time-series events (`sim_events`) and static vessel metadata (`vessels`).
- **Asynchronous Simulation**: The backend utilizes an asynchronous playback loop that windows historical data into 15-minute intervals, simulating a real-time sensor feed.

### 2. AI Predictive Engine (ETA)
- **Model**: A RandomForestRegressor (`eta_model.pkl`) is integrated for real-time inference.
- **Feature Vector**: Predictions are based on a 3-dimensional feature set:
    - **distance_to_port**: Calculated via the Haversine formula from current coordinates to the port center.
    - **effective_speed**: The vessel's Speed Over Ground (SOG) after accounting for environmental penalties and synthetic anomalies.
    - **inv_speed**: An inverse speed metric (`1 / (SOG + 0.1)`) utilized to ensure model stability and high-resolution arrival probability.

### 3. Stability and Sanitization
- **Recursive JSON Cleaning**: To prevent API failures due to out-of-range floating-point values (NaN, Inf) commonly found in raw AIS data or AI regression outputs, the system employs a deep-sanitization layer (`sanitize_recursive`). This ensures all JSON responses remain standard-compliant.

## Operational Modes and Anomalies
The PDDS Command Center supports dynamic manipulation of the simulation state through global anomaly modes. These modes allow operators to test port resilience under non-ideal conditions.

### Global Anomaly Modes
- **NORMAL**: Adheres to historical AIS behavior.
- **STOP**: Forces all vessel SOG to 0.0 (simulating a total port halt).
- **SLOW**: Reduces all vessel SOG by 50% (simulating congestion or equipment failure).
- **FAST**: Increases all vessel SOG by 50% (simulating emergency clearance).

### Environmental Stressors
- **Weather Simulation**: Interactive "Storm Circles" can be positioned on the simulation grid. Vessels entering the storm radius suffer an automatic 80% reduction in SOG, which is dynamically reflected in their AI-calculated ETA.

## API Documentation

### Core Simulation Endpoints
- **GET /health**: Returns the system status and indicates if the simulation loop is active.
- **GET /simulation/state**: Provides the complete state of the simulation, including active ships, berth occupancy, weather coordinates, and the current anomaly mode.
- **POST /simulation/anomaly**: Updates the global anomaly mode.
    - Payload: `{ "mode": "STOP" | "SLOW" | "FAST" | "NORMAL" }`
- **POST /simulation/reset**: Terminates the current playback and resets the simulation timeline to the initial dataset state.
- **POST /start**: Initializes the background simulation loop using the earliest available historical timestamp.

### Infrastructure Management
- **POST /port/berth**: Adds a new berth to the port configuration with custom dimensions.
- **DELETE /port/berth/{id}**: Removes a berth by its unique identifier.

## Installation and Setup

### 1. Prerequisites
- Python 3.9 or higher
- MongoDB instance (local or remote)
- Node.js (for optional frontend visualization)

### 2. Environment Configuration
Create a `.env` file in the project root with the following variables:
```env
MONGO_URL=mongodb://your_username:your_password@localhost:27017/port_simulation
```

### 3. Backend Deployment
```bash
# Initialize virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install fastapi uvicorn motor pandas pickle-mixin scikit-learn python-dotenv pydantic requests
```

### 4. Database Preparation
Ensure the `port_simulation` database contains the `sim_events` and `vessels` collections. Data must be in an ISODate format for the playback engine to function correctly.

## Usage and Verification

### Running the API
```bash
# Execute the FastAPI server
python3 api/main.py
```

### Automated Verification
A dedicated verification script is provided to test the "Perfect API" features, including simulation startup and anomaly injection.
```bash
# Ensure the backend is running, then execute:
python3 scripts/verify_api.py
```
This script will programmatically start the simulation, monitor vessel population, and verify that velocity modifiers are correctly applied in real-time.
