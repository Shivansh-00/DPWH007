# Smart Docking Decision Intelligence Engine

A full-stack, data-driven maritime simulation engine that replicates port operations using real AIS trajectory playback. 
Built using **FastAPI**, **React.js (Vite)**, and **MongoDB**, this framework features dynamic queue sequencing, turnaround-time optimized berth distribution, and visual metrics analysis.

## Features
- **Real-World AIS Playback**: Overrides procedural logic with timestamped mapping on approach paths.
- **Queue Reshuffling Constraints**: Ships are sequenced into Anchorage wait-zones until dynamic policy approvals trigger.
- **Deadlock Management**: Checks port capacities and attempts smart pre-assignments.
- **Glassmorphic Interactive Dashboard**: Configured with live event tickers and zone tracking visual layouts.

## Requirements
- Docker
- Docker Compose

## Quick Start (Dockerized)

This setup is fully portable. The Docker cluster spins up the **FastAPI Backend**, the **Vite/Nginx Frontend**, and an isolated **MongoDB container** equipped with persistent volumes.

```bash
# 1. Build the Docker cluster
docker-compose build

# 2. Run the environment
docker-compose up -d
```

### Self-Seeding Database
On its very first boot, the backend container detects if its internal MongoDB is empty. If it is, the backend will automatically parse `data/ais_raw.csv` and chunk load **150,000 real AIS coordinates** into the database. You'll see a console log when seeding is complete. Let it finish mapping the vectors before running heavy simulation starts.

### Accessing the Application
- **Frontend UI**: [http://localhost:5173](http://localhost:5173) *(Via local port proxy)*
- **Backend API**: [http://localhost:8000/docs](http://localhost:8000/docs) *(Swagger UI)*
- **Database**: Port `27017` is exposed locally. Connect using MongoDB Compass at `mongodb://localhost:27017/`.

---

## Local Development (Without Docker)

You can run the engine directly hooked into your host MongoDB.

**Setup Anaconda environment:**
```bash
conda create -n snackk python=3.11
conda activate snackk
pip install -r requirements.txt
```

**Seed Local Database:**
```bash
python -m data_pipeline.data_loader
```

**1. Run Backend Server**
```bash
python -m backend.main
```

**2. Run Frontend Server**
```bash
cd frontend
npm install
npm run dev
```
