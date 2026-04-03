import asyncio
import os
import random
from typing import List, Dict, Optional

from dotenv import load_dotenv
from fastapi import FastAPI, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel

load_dotenv()

app = FastAPI(title="Port Docking Decision System API")

# Add CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all for local dev
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

client = AsyncIOMotorClient(os.getenv("MONGO_URL"))
db = client["port_simulation"]

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


class SimulationContext:
    def __init__(self):
        self.berths: List[Berth] = []
        self.active_ships: Dict[int, dict] = {}
        self.anchorage_queue: List[int] = []
        self.port_channel: List[int] = []
        self.is_running = False
        self.ticks = 0


sim_ctx = SimulationContext()


@app.on_event("startup")
async def startup_db_client():
    sim_ctx.berths = [
        Berth(id=i, length=200 + random.randint(0, 200), width=30 + random.randint(0, 40))
        for i in range(1, 6)
    ]


@app.get("/simulation/state")
async def get_sim_state():
    ret = {
        "ticks": sim_ctx.ticks,
        "berths": sim_ctx.berths,
        "ships": list(sim_ctx.active_ships.values()),
        "anchorage_count": len(sim_ctx.anchorage_queue),
        "channel_count": len(sim_ctx.port_channel)
    }
    for _ in range(len(ret["ships"])):
        ret["ships"][_]["meta"].pop("_id", None)
    print(ret)
    return ret


@app.post("/start")
async def start_simulation(background_tasks: BackgroundTasks):
    if not sim_ctx.is_running:
        sim_ctx.is_running = True
        background_tasks.add_task(run_sim_loop)
    return {"status": "started"}


async def get_priority_score(vessel_meta: dict, wait_time: int):
    base = vessel_meta.get("priority", 5)
    score = (base * 100) - (wait_time * 2)
    return max(0, score)


async def control_entry_sequence():
    """
    Core Logic: Decide which ships from Anchorage enter the Port Channel.
    """
    if not sim_ctx.anchorage_queue:
        return

    candidates = []
    for mmsi in sim_ctx.anchorage_queue:
        ship = sim_ctx.active_ships[mmsi]
        score = await get_priority_score(ship["meta"], ship["wait_ticks"])
        candidates.append({"mmsi": mmsi, "score": score})

    candidates.sort(key=lambda x: x["score"])

    free_berths = sum(1 for b in sim_ctx.berths if b.occupied_by is None)
    cleared_limit = free_berths + 2

    if len(sim_ctx.port_channel) < cleared_limit:
        best_mmsi = candidates[0]["mmsi"]
        sim_ctx.anchorage_queue.remove(best_mmsi)
        sim_ctx.port_channel.append(best_mmsi)
        sim_ctx.active_ships[best_mmsi]["state"] = STATE_CLEARED
        print(f"SHIP {best_mmsi} CLEARED FOR ENTRY (PRIORITY)")


async def run_sim_loop():
    print("ENTRY: Simulation Loop Started")
    cursor = db.vessels.find({}).limit(50)
    vessels = await cursor.to_list(length=50)

    for v in vessels:
        mmsi = v["mmsi"]
        sim_ctx.active_ships[mmsi] = {
            "mmsi": mmsi,
            "meta": v,
            "state": STATE_APPROACHING,
            "pos": {"x": random.randint(0, 100), "y": random.randint(0, 800)},
            "wait_ticks": 0
        }

    while sim_ctx.is_running:
        sim_ctx.ticks += 1

        for mmsi, ship in sim_ctx.active_ships.items():
            if ship["state"] == STATE_APPROACHING:
                ship["pos"]["x"] += 5
                if ship["pos"]["x"] > 200:
                    ship["state"] = STATE_WAITING
                    sim_ctx.anchorage_queue.append(mmsi)

            elif ship["state"] == STATE_WAITING:
                ship["wait_ticks"] += 1

            elif ship["state"] == STATE_CLEARED:
                ship["pos"]["x"] += 3
                if ship["pos"]["x"] > 600:
                    for berth in sim_ctx.berths:
                        if (berth.occupied_by is None and
                                berth.length >= ship["meta"]["length"] and
                                berth.width >= ship["meta"]["width"]):
                            berth.occupied_by = mmsi
                            berth.status = "Occupied"
                            ship["state"] = STATE_DOCKED
                            sim_ctx.port_channel.remove(mmsi)
                            break

            elif ship["state"] == STATE_DOCKED:
                if random.random() < 0.05:
                    for b in sim_ctx.berths:
                        if b.occupied_by == mmsi:
                            b.occupied_by = None
                            b.status = "Empty"
                            break
                    ship["state"] = "DEPARTED"

        await control_entry_sequence()

        await asyncio.sleep(1)

    print("EXIT: Simulation Loop Stopped")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
