"""
Simulation API — WebSocket + REST Endpoints

Endpoints:
  WS  /ws/simulation       → Live simulation tick stream
  POST /api/simulation/start → Start simulation with config
  POST /api/simulation/pause → Pause
  POST /api/simulation/resume → Resume
  POST /api/simulation/reset → Reset
  POST /api/simulation/speed → Set playback speed
  GET  /api/simulation/state → Current state snapshot
  GET  /api/simulation/metrics → Current metrics
  GET  /api/queue              → Queue snapshot
"""

import asyncio
import json
from typing import List, Optional
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from backend.services.simulation_controller import SimulationController
from backend.models.schemas import SimulationTickPayload, ScoringWeights, ShipType
from backend.services.queue_manager import get_queue_snapshot
from backend.utils.logger import logger

import sys
sys.path.insert(0, "..")
from data_pipeline.scenario_generator import ScenarioGenerator


router = APIRouter()

# ─── Global Simulation Instance ──────────────────────────────────────────────

sim_controller = SimulationController()
connected_clients: List[WebSocket] = []


# ─── Request Models ──────────────────────────────────────────────────────────

class StartSimulationRequest(BaseModel):
    scenario: str = "mixed"  # "mixed", "weather_cluster", "port_congestion", "emergency"
    berth_count: int = 6
    ship_count: int = 15
    seed: int = 42
    playback_speed: float = 1.0
    policy_mode: str = "SCORING"  # "SCORING", "FCFS", "PRIORITY_ONLY"

    # Scenario-specific params
    storm_intensity: float = 0.8
    congestion_level: float = 0.9

    # Custom scoring weights (optional)
    weights: Optional[ScoringWeights] = None

    # Custom berths (optional — if not provided, auto-generated)
    custom_berths: Optional[list] = None

class SpeedRequest(BaseModel):
    speed: float

class AnomalyRequest(BaseModel):
    mode: str  # NORMAL, STOP, SLOW, FAST

class WeatherCenter(BaseModel):
    x: float
    y: float

class WeatherRequest(BaseModel):
    center: Optional[WeatherCenter] = None
    radius: float = 100.0


# ─── WebSocket Broadcast ─────────────────────────────────────────────────────

async def broadcast_payload(payload: SimulationTickPayload):
    """Send simulation state to all connected WebSocket clients."""
    data = payload.model_dump_json()
    disconnected = []
    for ws in connected_clients:
        try:
            await ws.send_text(data)
        except Exception:
            disconnected.append(ws)

    for ws in disconnected:
        connected_clients.remove(ws)


# ─── WebSocket Endpoint ──────────────────────────────────────────────────────

@router.websocket("/ws/simulation")
async def websocket_simulation(websocket: WebSocket):
    await websocket.accept()
    connected_clients.append(websocket)
    logger.info(f"WebSocket client connected. Total: {len(connected_clients)}")

    try:
        while True:
            # Listen for client messages (control commands)
            data = await websocket.receive_text()
            msg = json.loads(data)
            cmd = msg.get("command", "")

            if cmd == "pause":
                sim_controller.pause()
            elif cmd == "resume":
                sim_controller.resume()
            elif cmd == "speed":
                sim_controller.set_speed(msg.get("value", 1.0))
            elif cmd == "reset":
                sim_controller.reset()

    except WebSocketDisconnect:
        connected_clients.remove(websocket)
        logger.info(f"WebSocket client disconnected. Remaining: {len(connected_clients)}")


# ─── REST Endpoints ──────────────────────────────────────────────────────────

@router.post("/api/simulation/start")
async def start_simulation(req: StartSimulationRequest):
    """Configure and start the simulation with a chosen scenario."""
    gen = ScenarioGenerator(seed=req.seed)

    playback_buffer = {}
    
    # Generate ships based on scenario
    if req.scenario == "weather_cluster":
        ships = gen.weather_cluster_scenario(
            ship_count=req.ship_count,
            storm_intensity=req.storm_intensity,
        )
        berths = gen.generate_default_berths(req.berth_count)

    elif req.scenario == "port_congestion":
        ships, berths = gen.port_congestion_scenario(
            incoming_ships=req.ship_count,
            berth_count=req.berth_count,
            congestion_level=req.congestion_level,
        )

    elif req.scenario == "emergency":
        ships = gen.emergency_scenario(normal_ships=req.ship_count)
        berths = gen.generate_default_berths(req.berth_count)

    else:  # "mixed" now uses AIS playback
        ships, playback_buffer = gen.load_ais_playback(ship_count=req.ship_count)
        berths = gen.generate_default_berths(req.berth_count)

    # Configure
    sim_controller.configure(
        ships=ships,
        berths=berths,
        weights=req.weights or ScoringWeights(),
        policy_mode=req.policy_mode,
        playback_speed=req.playback_speed,
        playback_buffer=playback_buffer,  # Pass real trajectory data
    )
    sim_controller.set_broadcast_callback(broadcast_payload)

    # Start in background
    asyncio.create_task(sim_controller.start())

    return {
        "status": "started",
        "scenario": req.scenario,
        "ships": len(ships),
        "berths": len(berths),
        "policy": req.policy_mode,
        "speed": req.playback_speed,
        "anomaly_mode": sim_controller.anomaly_mode,
        "weather_center": sim_controller.weather_center
    }


@router.post("/api/simulation/pause")
async def pause_simulation():
    sim_controller.pause()
    return {"status": "paused"}


@router.post("/api/simulation/resume")
async def resume_simulation():
    sim_controller.resume()
    return {"status": "resumed"}


@router.post("/api/simulation/reset")
async def reset_simulation():
    sim_controller.reset()
    return {"status": "reset"}


@router.post("/api/simulation/speed")
async def set_speed(req: SpeedRequest):
    sim_controller.set_speed(req.speed)
    return {"status": "speed_set", "speed": req.speed}


@router.post("/api/simulation/anomaly")
async def set_anomaly(req: AnomalyRequest):
    mode = req.mode.upper()
    if mode in ["NORMAL", "STOP", "SLOW", "FAST"]:
        sim_controller.anomaly_mode = mode
        return {"status": "anomaly updated", "mode": mode}
    return {"status": "error", "message": "Invalid anomaly mode"}


@router.post("/api/simulation/weather")
async def set_weather(req: WeatherRequest):
    if req.center:
        sim_controller.weather_center = {"x": req.center.x, "y": req.center.y}
        sim_controller.weather_radius = req.radius
        return {"status": "weather updated", "center": req.center.model_dump(), "radius": req.radius}
    else:
        sim_controller.weather_center = None
        return {"status": "weather cleared"}


@router.get("/api/simulation/state")
async def get_state():
    """Return the full current simulation state."""
    return {
        "clock_ms": sim_controller.global_clock_ms,
        "is_running": sim_controller.is_running,
        "is_paused": sim_controller.is_paused,
        "speed": sim_controller.playback_speed,
        "ships": [s.model_dump() for s in sim_controller.ships],
        "berths": [b.model_dump() for b in sim_controller.berths],
    }


@router.get("/api/simulation/metrics")
async def get_metrics():
    """Return current performance metrics."""
    return sim_controller._compute_snapshot_metrics()


@router.get("/api/queue")
async def get_queue():
    """Return the current queue state for debugging / display."""
    return get_queue_snapshot(sim_controller.ships)
