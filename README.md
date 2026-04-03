# TEAM: DPWH007

# Port Docking Decision System (PDDS)

PDDS is an intelligent maritime simulation and decision-support tool designed to optimize the docking process for
incoming vessels. By prioritizing ships based on cargo type (e.g., Food > Tanker) and managing port entry through a
controlled anchorage-to-channel sequence, PDDS reduces congestion and waiting times.

## Features

- **AIS Data Integration**: Processes raw AIS datasets, cleaning and enriching them with vessel metadata.
- **Priority-Based Docking**: Implements a scoring system (Food > Tanker > Roll-on > Container > Bulk Carrier).
- **Zone-Based Control**: Real-world simulation of Open Sea, Anchorage, Port Channel, and Berths.
- **Risk Simulation**: Injects synthetic operational risks (Weather, Geopolitical) to test port resilience.
- **Interactive Dashboard**: A premium Next.js dashboard with real-time ship tracking and berth management.

## Tech Stack

- **Backend**: FastAPI (Python), Motor (Async MongoDB Driver).
- **Frontend**: Next.js, React, Framer Motion, Lucide Icons, Vanilla CSS.
- **Database**: MongoDB.
- **Tools**: Pandas (Data Cleaning), Uvicorn.

---

## Setup Instructions

### 1. Prerequisites

- Python 3.9+
- Node.js 18+
- MongoDB Running locally (or a connection string)
- Conda or venv

### 2. Environment Configuration

Create a `.env` file in the root directory:

```env
MONGO_URL=mongodb://your_user:your_password@localhost:27017/admin
```

### 3. Backend Setup

```bash
# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install pandas matplotlib seabed seaborn motor fastapi uvicorn pymongo python-dotenv pydantic
```

### 4. Frontend Setup

```bash
cd frontend
npm install
```

---

## How to Run

### Step 1: Data Cleaning & Ingestion

First, clean the raw AIS data and push it to MongoDB:

```bash
# Assuming Python environment is active
python3 clean_data.py   # Cleans local ais_raw.csv
python3 ingest_data.py  # Enriches data and syncs to MongoDB
```

### Step 2: Start the Backend

```bash
python3 api/main.py
```

The API will be available at `http://localhost:8000`. You can view the docs at `/docs`.

### Step 3: Start the Frontend

```bash
cd frontend
npm run dev -- --hostname 0.0.0.0
```

Open `http://localhost:3001` (or your local IP provided by the CLI) in your browser.

---

## Simulation Logic

1. **APPROACHING**: Ships move from the Open Sea towards the port boundary.
2. **WAITING**: Once they cross the boundary, they enter the **Anchorage Zone**.
3. **CLEARED**: The Decision Engine picks the highest priority ship from the Anchorage queue if a berth is likely to be
   available.
4. **DOCKED**: Ships enter the **Port Channel** and proceed to a matching **Berth** based on length/width constraints.

## Priority Scoring

- **Food Ships**: Priority 1 (Perishable) - Red
- **Tankers**: Priority 2 (Hazardous) - Yellow
- **General Cargo/Others**: Priority 3-5 - Blue
