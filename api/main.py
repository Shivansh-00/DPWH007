import asyncio
import os
import random
import math
import pickle
import pandas as pd
from datetime import datetime, timedelta
from contextlib import asynccontextmanager
from typing import List, Dict, Optional

from dotenv import load_dotenv
from fastapi import FastAPI, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel

load_dotenv()

client = AsyncIOMotorClient(os.getenv("MONGO_URL"))
db = client["port_simulation"]

try:
    with open("eta_model.pkl", "rb") as f:
        pdds_model = pickle.load(f)
except FileNotFoundError:
    with open("../eta_model.pkl", "rb") as f:
        pdds_model = pickle.load(f)

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


STATE_APPROACHING = "APPROACHING"
STATE_WAITING = "WAITING"
STATE_CLEARED = "CLEARED"
STATE_DOCKED = "DOCKED"


class Berth(BaseModel):
    id: int
    length: float
    width: float
    occupied_by: Optional[int] = None
    status: str = "Empty"


LAT_MIN, LAT_MAX = 24.0, 31.0
LON_MIN, LON_MAX = -98.0, -80.0


def map_to_pixels(lat, lon):
    x = (lon - LON_MIN) / (LON_MAX - LON_MIN) * 800
    y = (lat - LAT_MIN) / (LAT_MAX - LAT_MIN) * 600
    return {"x": float(x), "y": 600 - float(y)}


class SimulationContext:
    def __init__(self):
        self.berths: List[Berth] = []
        self.active_ships: Dict[int, dict] = {}
        self.is_running = False
        self.current_time = None
        self.ticks = 0
        self.weather_center: Optional[Dict[str, float]] = None
        self.weather_radius: float = 100.0
        self.anomaly_mode: str = "NORMAL"  # "NORMAL", "STOP", "SLOW", "FAST"


sim_ctx = SimulationContext()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup logic
    sim_ctx.berths = [
        Berth(id=i, length=200 + random.randint(0, 200), width=30 + random.randint(0, 40))
        for i in range(1, 8)
    ]
    yield
    # Shutdown logic (could close DB here)

app = FastAPI(title="Port Docking Decision System API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def sanitize_recursive(obj):
    """Deeply sanitize a dictionary/list for JSON compliance"""
    if isinstance(obj, dict):
        return {k: sanitize_recursive(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [sanitize_recursive(i) for i in obj]
    elif isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            return 0.0
        return obj
    return obj


def sanitize_float(v, default=0.0):
    """Ensure float is JSON compliant (no NaN/Inf)"""
    try:
        val = float(v)
        if math.isnan(val) or math.isinf(val):
            return default
        return val
    except:
        return default


@app.get("/simulation/state")
async def get_sim_state():
    data = {
        "current_time": str(sim_ctx.current_time) if sim_ctx.current_time else "Not Started",
        "berths": [b.model_dump() for b in sim_ctx.berths], # Ensure Pydantic model is dict
        "ships": list(sim_ctx.active_ships.values()),
        "bounds": {"lat": [LAT_MIN, LAT_MAX], "lon": [LON_MIN, LON_MAX]},
        "weather": {"center": sim_ctx.weather_center, "radius": sim_ctx.weather_radius},
        "anomaly_mode": sim_ctx.anomaly_mode
    }
    return sanitize_recursive(data)


@app.post("/simulation/weather")
async def update_weather(data: dict):
    sim_ctx.weather_center = data.get("center")
    sim_ctx.weather_radius = sanitize_float(data.get("radius", 100.0), 100.0)
    return {"status": "updated"}


@app.post("/port/berth")
async def add_berth(berth: Berth):
    sim_ctx.berths.append(berth)
    return {"status": "added"}


@app.post("/simulation/anomaly")
async def set_anomaly(data: dict):
    mode = data.get("mode", "NORMAL").upper()
    if mode in ["NORMAL", "STOP", "SLOW", "FAST"]:
        sim_ctx.anomaly_mode = mode
        return {"status": "anomaly updated", "mode": mode}
    return {"status": "error", "message": "Invalid anomaly mode"}


@app.post("/simulation/reset")
async def reset_simulation():
    sim_ctx.current_time = None
    sim_ctx.active_ships = {}
    sim_ctx.is_running = False
    return {"status": "reset complete"}


@app.get("/health")
async def health():
    return {"status": "healthy", "sim_running": sim_ctx.is_running}


@app.post("/start")
async def start_simulation(background_tasks: BackgroundTasks):
    if not sim_ctx.is_running:
        first_event = await db.sim_events.find_one(sort=[("base_date_time", 1)])
        if first_event:
            if isinstance(first_event["base_date_time"], str):
                sim_ctx.current_time = datetime.fromisoformat(first_event["base_date_time"])
            else:
                sim_ctx.current_time = first_event["base_date_time"]

        sim_ctx.is_running = True
        background_tasks.add_task(run_playback_loop)
    return {"status": "started", "time": str(sim_ctx.current_time)}


async def run_playback_loop():
    print(f"PLAYBACK: Started from {sim_ctx.current_time}")

    vessels_cursor = db.vessels.find({})
    vessel_meta = {}
    async for v in vessels_cursor:
        v.pop("_id", None)  # Ensure non-serializable ObjectId is removed
        vessel_meta[v["mmsi"]] = v

    while sim_ctx.is_running:
        window_start = sim_ctx.current_time
        window_end = window_start + timedelta(minutes=15)

        cursor = db.sim_events.find({
            "base_date_time": {"$gte": window_start, "$lt": window_end}
        }).sort("base_date_time", 1)

        events = await cursor.to_list(length=1000)
        seen_this_tick = set()
        for event in events:
            mmsi = event["mmsi"]
            seen_this_tick.add(mmsi)

            lat = sanitize_float(event.get("latitude"), PORT_LAT)
            lon = sanitize_float(event.get("longitude"), PORT_LON)
            pos = map_to_pixels(lat, lon)
            dist_to_port = sanitize_float(haversine(lat, lon, PORT_LAT, PORT_LON))

            sog = sanitize_float(event.get("sog"), 0.0)
            cog = sanitize_float(event.get("cog"), 0.0)
            
            # Global Anomaly Modifiers
            if sim_ctx.anomaly_mode == "STOP":
                sog = 0.0
            elif sim_ctx.anomaly_mode == "SLOW":
                sog *= 0.5
            elif sim_ctx.anomaly_mode == "FAST":
                sog *= 1.5

            in_storm = False
            if sim_ctx.weather_center:
                dx = pos["x"] - sim_ctx.weather_center["x"]
                dy = pos["y"] - sim_ctx.weather_center["y"]
                d_px = (dx ** 2 + dy ** 2) ** 0.5
                if d_px < sim_ctx.weather_radius:
                    sog *= 0.2
                    in_storm = True

            # New model features: distance_to_port, effective_speed, inv_speed
            inv_speed = 1.0 / (sog + 0.1)
            features_df = pd.DataFrame([[dist_to_port, sog, inv_speed]], 
                                     columns=['distance_to_port', 'effective_speed', 'inv_speed'])
            
            try:
                ai_eta = sanitize_float(float(pdds_model.predict(features_df)[0]))
            except:
                ai_eta = 0.0

            state = STATE_APPROACHING
            if dist_to_port < 5.0 and sog > 1.0:
                state = STATE_WAITING
            elif dist_to_port < 1.0 and sog < 1.0:
                state = STATE_DOCKED

            if mmsi not in sim_ctx.active_ships:
                sim_ctx.active_ships[mmsi] = {
                    "mmsi": mmsi,
                    "meta": vessel_meta.get(mmsi, {"vessel_name": "Unknown", "priority": 3}),
                    "docked_ticks": 0
                }

            ship = sim_ctx.active_ships[mmsi]
            ship.update({
                "state": state,
                "pos": pos,
                "lat": lat,
                "lon": lon,
                "sog": sog,
                "ai_eta": ai_eta,
                "in_storm": in_storm,
                "last_seen": sim_ctx.current_time,
                "timestamp": str(event["base_date_time"])
            })

        mmsis_to_remove = []
        for mmsi, ship in sim_ctx.active_ships.items():
            time_since_seen = (sim_ctx.current_time - ship["last_seen"]).total_seconds()
            if time_since_seen > 7200:
                mmsis_to_remove.append(mmsi)
                continue

            ship_lat, ship_lon = ship.get("lat"), ship.get("lon")
            if ship_lat and (ship_lat < LAT_MIN or ship_lat > LAT_MAX or ship_lon < LON_MIN or ship_lon > LON_MAX):
                mmsis_to_remove.append(mmsi)
                continue

            if ship["state"] == STATE_DOCKED:
                ship["docked_ticks"] += 1
                if ship["docked_ticks"] > 8:
                    for berth in sim_ctx.berths:
                        if berth.occupied_by == mmsi:
                            berth.occupied_by = None
                            berth.status = "Empty"
                    mmsis_to_remove.append(mmsi)

        for mmsi in mmsis_to_remove:
            del sim_ctx.active_ships[mmsi]

        sim_ctx.current_time = window_end
        await asyncio.sleep(1)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
