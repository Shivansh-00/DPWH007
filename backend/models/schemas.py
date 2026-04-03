"""
Core data models for the Smart Docking Decision Intelligence Engine.

Zone-Based Model:
  OPEN_SEA → APPROACHING → WAITING (anchorage) → CLEARED_TO_ENTER → IN_CHANNEL → DOCKED → COMPLETED
"""

from pydantic import BaseModel, ConfigDict, Field
from typing import Optional, List, Literal
from enum import Enum


# ─── Ship States (Zone-Based) ────────────────────────────────────────────────

class ShipZone(str, Enum):
    OPEN_SEA = "OPEN_SEA"              # No port control
    APPROACHING = "APPROACHING"        # Crossed boundary, detected by system
    WAITING = "WAITING"                # Held in anchorage zone
    CLEARED_TO_ENTER = "CLEARED_TO_ENTER"  # Port authority cleared entry
    IN_CHANNEL = "IN_CHANNEL"          # Inside port entry channel (order is FIXED)
    DOCKED = "DOCKED"                  # Occupying a berth
    COMPLETED = "COMPLETED"            # Unloading/loading done, departed


class ShipType(str, Enum):
    CONTAINER = "Container"
    BULK_CARRIER = "Bulk Carrier"
    TANKER = "Tanker"
    ROLL_ON = "Roll-On"
    FOOD = "Food"


# ─── Cargo Priority Mapping ──────────────────────────────────────────────────
# Higher value = higher urgency

CARGO_PRIORITY_MAP = {
    ShipType.FOOD: 1.0,          # Perishable, highest urgency
    ShipType.TANKER: 0.8,        # Spill risk
    ShipType.ROLL_ON: 0.5,       # Vehicles, moderate
    ShipType.BULK_CARRIER: 0.3,  # Raw materials, low urgency
    ShipType.CONTAINER: 0.2,     # General goods, lowest urgency
}


# ─── Dynamic Scoring Weights (Tunable) ───────────────────────────────────────

class ScoringWeights(BaseModel):
    """Normalized weights for the priority scoring function. Sum should be ~1.0"""
    cargo_priority: float = 0.30
    waiting_time: float = 0.25
    eta_urgency: float = 0.20
    risk_factor: float = 0.15
    fuel_criticality: float = 0.10


# ─── Ship Model ──────────────────────────────────────────────────────────────

class Ship(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    ship_id: int
    name: str = ""
    ship_type: ShipType
    zone: ShipZone = ShipZone.OPEN_SEA

    # Physical attributes
    length_m: float = 200.0
    draft_m: float = 12.0          # How deep the ship sits in water

    # Navigation state
    position_x: float = 0.0       # Grid X coordinate (0 = far left, increases toward dock)
    position_y: float = 0.0       # Grid Y coordinate
    speed_knots: float = 10.0     # Original programmed speed
    effective_speed_knots: Optional[float] = None # Adjusted speed (weather, traffic)
    heading_deg: float = 90.0     # Direction of travel

    # Distance / Time calculations
    distance_to_boundary: float = 100.0   # km to boundary
    distance_to_berth: float = 150.0      # km to nearest compatible berth
    eta_minutes: float = 60.0             # Estimated time of arrival

    # Scoring inputs (all normalized 0–1)
    cargo_priority: float = 0.2
    waiting_time_normalized: float = 0.0
    eta_urgency_normalized: float = 0.0
    fuel_criticality: float = 0.0   # 0 = full tank, 1 = critical
    risk_factor: float = 0.0        # 0 = safe, 1 = extreme risk

    # Computed score
    priority_score: float = 0.0

    # Timing
    waiting_since_ms: Optional[int] = None   # When the ship entered anchorage
    timestamp_ms: int = 0                    # Last state update time

    # Berth assignment
    assigned_berth_id: Optional[int] = None
    assignment_reason: str = ""

    # Cargo details
    cargo_tons: float = 5000.0
    cargo_remaining_pct: float = 100.0       # % of cargo yet to unload/load
    estimated_processing_hours: float = 8.0  # Time to fully unload/load


# ─── Berth Model ─────────────────────────────────────────────────────────────

class Berth(BaseModel):
    berth_id: int
    name: str = ""
    status: Literal["Free", "Occupied"] = "Free"

    # Physical constraints
    max_draft_m: float = 15.0
    length_m: float = 350.0
    position_x: float = 0.0     # Grid position of the berth (right side of screen)
    position_y: float = 0.0

    # Equipment compatibility
    equipment_types: List[str] = []  # ["Cranes", "Pipes", "Ramps", "Refrigeration"]

    # Occupancy tracking
    currently_docked_ship_id: Optional[int] = None
    estimated_free_time_ms: Optional[int] = None
    cargo_processed_pct: float = 0.0


# ─── Equipment Compatibility Map ─────────────────────────────────────────────

SHIP_EQUIPMENT_REQUIREMENTS = {
    ShipType.CONTAINER: ["Cranes"],
    ShipType.BULK_CARRIER: ["Cranes"],
    ShipType.TANKER: ["Pipes"],
    ShipType.ROLL_ON: ["Ramps"],
    ShipType.FOOD: ["Cranes", "Refrigeration"],
}


# ─── Simulation Event Log ────────────────────────────────────────────────────

class SimulationEvent(BaseModel):
    timestamp_ms: int
    event_type: str  # "QUEUE_DECISION", "RESHUFFLE", "BERTH_ASSIGNMENT", "ANOMALY", "ZONE_TRANSITION"
    ship_id: Optional[int] = None
    berth_id: Optional[int] = None
    details: str = ""
    priority_score: Optional[float] = None


# ─── WebSocket Payload ────────────────────────────────────────────────────────

class SimulationTickPayload(BaseModel):
    """Sent to the frontend every simulation tick via WebSocket."""
    clock_ms: int
    ships: List[Ship]
    berths: List[Berth]
    events: List[SimulationEvent] = []
    metrics: dict = {}
    anomaly_mode: str = "NORMAL"
    weather_center: Optional[dict] = None
