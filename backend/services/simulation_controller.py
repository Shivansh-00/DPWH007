"""
Simulation Controller — Global Clock, Playback, and Orchestration

Responsibilities:
  1. Maintain a global simulation clock (virtual time in ms).
  2. Support pause / resume / reset / adjustable speed (1x, 2x, 5x, 10x).
  3. On each tick:
     a) Move ships forward based on speed and elapsed time.
     b) Detect boundary crossings (APPROACHING → WAITING).
     c) Run queue scoring + entry sequencing.
     d) Run berth assignment.
     e) Update berth processing progress.
     f) Collect metrics.
     g) Broadcast state via WebSocket callback.

This module is the single orchestrator that ties queue_manager,
berth_assigner, and the data layer together.
"""

import asyncio
import time
import os
import pickle
import pandas as pd
import random
from typing import List, Callable, Awaitable, Optional

try:
    with open("backend/models/eta_model.pkl", "rb") as f:
        ai_eta_model = pickle.load(f)
except Exception as e:
    print(f"Warning: Failed to load ETA model: {e}")
    ai_eta_model = None

from backend.models.schemas import (
    Ship, Berth, ShipZone, ShipType, ScoringWeights,
    SimulationEvent, SimulationTickPayload, CARGO_PRIORITY_MAP
)
from backend.services.queue_manager import (
    control_entry_sequence,
    transition_approaching_to_waiting,
    transition_cleared_to_channel,
    update_waiting_times,
    score_all_ships,
)
from backend.services.berth_assigner import (
    assign_berths,
    update_berth_progress,
)
from backend.utils.logger import logger


# ─── Simulation Zone Distances (grid units) ──────────────────────────────────

BOUNDARY_DISTANCE = 300.0       # Distance from dock where ships are first detected
CHANNEL_ENTRY_DISTANCE = 50.0   # Distance from dock where the entry channel begins
DOCK_DISTANCE = 0.0             # At the dock


class SimulationController:
    """
    Drives the simulation forward, one tick at a time.
    """

    def __init__(self):
        # Clock
        self.global_clock_ms: int = 0
        self.tick_count: int = 0

        # Playback
        self.is_running: bool = False
        self.is_paused: bool = False
        self.playback_speed: float = 1.0
        self.tick_interval_seconds: float = 1.0  # Real-time seconds between ticks
        self.virtual_seconds_per_tick: float = 60.0  # 1 tick = 1 virtual minute

        # State
        self.ships: List[Ship] = []
        self.berths: List[Berth] = []
        self.events_log: List[SimulationEvent] = []
        self.scoring_weights: ScoringWeights = ScoringWeights()

        # Simulation mode
        self.policy_mode: str = "SCORING"  # "SCORING", "FCFS", "PRIORITY_ONLY"

        # Anomalies
        self.anomaly_mode: str = "NORMAL"
        self.weather_center: Optional[dict] = None
        self.weather_radius: float = 100.0

        # Metrics accumulator
        self.metrics: dict = {
            "total_ships_processed": 0,
            "total_reshuffles": 0,
            "total_deadlocks": 0,
            "avg_waiting_time_min": 0.0,
            "berth_utilization_pct": 0.0,
            "fuel_wastage_estimate": 0.0,
            "queue_length_history": [],        # [(clock_ms, length)]
            "turnaround_by_type": {},          # {ShipType: [minutes]}
            "throughput_per_hour": 0.0,
        }

        # Callback: called every tick with the full state payload
        self._broadcast_callback: Optional[Callable[[SimulationTickPayload], Awaitable[None]]] = None

    # ─── Setup ─────────────────────────────────────────────────────────────

    def configure(
        self,
        ships: List[Ship],
        berths: List[Berth],
        weights: Optional[ScoringWeights] = None,
        policy_mode: str = "SCORING",
        playback_speed: float = 1.0,
        playback_buffer: Optional[dict] = None,
    ):
        """Initialize simulation state before starting."""
        self.ships = ships
        self.berths = berths
        self.scoring_weights = weights or ScoringWeights()
        self.policy_mode = policy_mode
        self.playback_speed = playback_speed
        self._playback_buffer = playback_buffer or {}
        self.global_clock_ms = 0
        self.tick_count = 0
        self.events_log = []
        self.anomaly_mode = "NORMAL"
        self.weather_center = None
        self.weather_radius = 100.0
        self.metrics = {
            "total_ships_processed": 0,
            "total_reshuffles": 0,
            "total_deadlocks": 0,
            "avg_waiting_time_min": 0.0,
            "berth_utilization_pct": 0.0,
            "fuel_wastage_estimate": 0.0,
            "queue_length_history": [],
            "turnaround_by_type": {},
            "throughput_per_hour": 0.0,
        }

    def set_broadcast_callback(self, callback: Callable[[SimulationTickPayload], Awaitable[None]]):
        """Register a WebSocket broadcast function."""
        self._broadcast_callback = callback

    # ─── Playback Controls ─────────────────────────────────────────────────

    def set_speed(self, speed: float):
        if speed > 0:
            self.playback_speed = speed
            logger.info(f"Playback speed set to {speed}x")

    def pause(self):
        self.is_paused = True
        logger.info("Simulation PAUSED")

    def resume(self):
        self.is_paused = False
        logger.info("Simulation RESUMED")

    def reset(self):
        self.is_running = False
        self.is_paused = False
        self.global_clock_ms = 0
        self.tick_count = 0
        logger.info("Simulation RESET")

    # ─── Main Loop ─────────────────────────────────────────────────────────

    async def start(self):
        """Start the simulation loop. Runs until stopped or all ships processed."""
        self.is_running = True
        self.is_paused = False
        logger.info("Simulation STARTED")

        while self.is_running:
            if self.is_paused:
                await asyncio.sleep(0.1)
                continue

            tick_events = self._tick()
            self.events_log.extend(tick_events)

            # Build payload and broadcast
            if self._broadcast_callback:
                payload = SimulationTickPayload(
                    clock_ms=self.global_clock_ms,
                    ships=self.ships,
                    berths=self.berths,
                    events=tick_events,
                    metrics=self._compute_snapshot_metrics(),
                    anomaly_mode=self.anomaly_mode,
                    weather_center=self.weather_center
                )
                try:
                    await self._broadcast_callback(payload)
                except Exception as e:
                    logger.warning(f"Broadcast failed: {e}")

            # Check completion
            active_ships = [s for s in self.ships if s.zone != ShipZone.COMPLETED]
            if not active_ships:
                logger.info("All ships processed. Simulation complete.")
                self.is_running = False
                break

            # Wait for next tick (adjusted by playback speed)
            wait_time = self.tick_interval_seconds / self.playback_speed
            await asyncio.sleep(max(0.05, wait_time))

    # ─── Tick Logic ────────────────────────────────────────────────────────

    def _tick(self) -> List[SimulationEvent]:
        """Advance the simulation by one step."""
        self.tick_count += 1
        self.global_clock_ms += int(self.virtual_seconds_per_tick * 1000)
        all_events: List[SimulationEvent] = []

        # Step 1: Move ships
        self._move_ships()

        # Step 2: Detect boundary crossings (APPROACHING → WAITING)
        self.ships, events = transition_approaching_to_waiting(
            self.ships, boundary_distance=0.0, current_clock_ms=self.global_clock_ms
        )
        all_events.extend(events)

        # Step 3: Run queue management (entry sequencing)
        available_berths = len([b for b in self.berths if b.status == "Free"])
        self.ships, events = control_entry_sequence(
            self.ships, available_berths, self.global_clock_ms, self.scoring_weights
        )
        all_events.extend(events)

        # Step 4: Move CLEARED ships into channel
        self.ships, events = transition_cleared_to_channel(
            self.ships, self.global_clock_ms
        )
        all_events.extend(events)

        # Step 5: Assign berths to IN_CHANNEL ships
        self.ships, self.berths, events = assign_berths(
            self.ships, self.berths, self.global_clock_ms
        )
        all_events.extend(events)

        # Step 6: Progress cargo at docked ships
        self.ships, self.berths, events = update_berth_progress(
            self.ships, self.berths,
            tick_seconds=self.virtual_seconds_per_tick,
            current_clock_ms=self.global_clock_ms
        )
        all_events.extend(events)

        # Step 7: Update metrics
        self._update_metrics(all_events)

        return all_events

    def _calculate_ai_eta(self, ship: Ship) -> float:
        eff_speed = ship.effective_speed_knots if ship.effective_speed_knots is not None else ship.speed_knots
        if eff_speed <= 0:
            return 0.0
            
        if ai_eta_model is not None:
            try:
                inv_speed = 1.0 / (eff_speed + 0.1)
                features_df = pd.DataFrame([
                    [ship.distance_to_boundary, eff_speed, inv_speed]
                ], columns=['distance_to_port', 'effective_speed', 'inv_speed'])
                return max(0.0, float(ai_eta_model.predict(features_df)[0]))
            except Exception as e:
                pass
                
        return max(0, (ship.distance_to_boundary / eff_speed) * 60)

    def _move_ships(self):
        """
        Advance ship positions based on speed each tick.
        For ships with AIS telemetry (trajectory), interpolate their positions based on 
        global clock + base_timestamp. Otherwise, fallback to linear pathing.
        Ships move right (toward dock) along the X axis.
        """
        elapsed_hours = self.virtual_seconds_per_tick / 3600.0

        for ship in self.ships:
            # Calculate effective speed
            eff_speed = ship.speed_knots
            if self.anomaly_mode == "STOP":
                eff_speed = 0.0
            elif self.anomaly_mode == "SLOW":
                eff_speed *= 0.5
            elif self.anomaly_mode == "FAST":
                eff_speed *= 1.5

            if self.weather_center:
                dx = ship.position_x - self.weather_center.get("x", 0)
                dy = ship.position_y - self.weather_center.get("y", 0)
                if (dx**2 + dy**2)**0.5 < self.weather_radius:
                    eff_speed *= 0.2
            
            # Enforce a floor speed for ships that SHOULD be moving (procedural or after AIS ends)
            # This prevents ships from getting stuck at permanent 0 knots if AIS last point was 0.
            if self.anomaly_mode != "STOP" and ship.zone in (ShipZone.OPEN_SEA, ShipZone.APPROACHING, ShipZone.CLEARED_TO_ENTER, ShipZone.IN_CHANNEL):
                if eff_speed < 2.0:
                    # Use a stable random speed based on ship_id to avoid "jittery" movement every tick
                    eff_speed = random.Random(ship.ship_id).uniform(3.0, 10.0)
            
            ship.effective_speed_knots = eff_speed

            # Replay AIS Data if available in buffer
            # We assume self._playback_buffer stores dicts map of ship_id -> list of (offset_ms, lat, lon, heading, speed)
            if hasattr(self, '_playback_buffer') and ship.ship_id in self._playback_buffer and ship.zone in (ShipZone.OPEN_SEA, ShipZone.APPROACHING):
                traj = self._playback_buffer[ship.ship_id]
                # Find the closest past point
                current_time = self.global_clock_ms
                closest = traj[0]
                for pt in traj:
                    if pt[0] <= current_time:
                        closest = pt
                    else:
                        break
                
                # Apply AIS data to ship physical attributes
                ship.speed_knots = closest[4]
                ship.heading_deg = closest[3]
                
                # Map lat/lon to X/Y for grid view
                # Let's say longitudes range heavily. We map directly to X,Y just for visual variance,
                # or we just use it to calculate real distance_to_boundary.
                
                # Simple visual mapping: lon -> x, lat -> y
                # (You would need bounds. For now, just reduce distance based on speed manually to trigger boundary)
                distance_covered = ship.effective_speed_knots * elapsed_hours
                ship.distance_to_boundary -= distance_covered
                ship.position_x += distance_covered * 2

                if ship.distance_to_boundary <= BOUNDARY_DISTANCE * 0.3:
                    ship.zone = ShipZone.APPROACHING

                # ETA recalculation
                if ship.zone == ShipZone.APPROACHING and ship.effective_speed_knots > 0:
                    ship.eta_minutes = self._calculate_ai_eta(ship)
            
            else:
                # Standard procedural movement
                if ship.zone == ShipZone.OPEN_SEA:
                    distance_covered = ship.effective_speed_knots * elapsed_hours
                    ship.distance_to_boundary -= distance_covered
                    ship.position_x += distance_covered * 2
    
                    if ship.distance_to_boundary <= BOUNDARY_DISTANCE * 0.3:
                        ship.zone = ShipZone.APPROACHING
    
                elif ship.zone == ShipZone.APPROACHING:
                    distance_covered = ship.effective_speed_knots * elapsed_hours
                    ship.distance_to_boundary -= distance_covered
                    ship.position_x += distance_covered * 2
    
                    if ship.effective_speed_knots > 0:
                        ship.eta_minutes = self._calculate_ai_eta(ship)

            # Common movement logic for controlled zones
            if ship.zone == ShipZone.WAITING:
                pass # Anchored

            elif ship.zone in (ShipZone.CLEARED_TO_ENTER, ShipZone.IN_CHANNEL):
                # Max 3 knots in channel
                channel_speed = min(ship.effective_speed_knots, 3.0)
                distance_covered = channel_speed * elapsed_hours
                ship.position_x += distance_covered * 2

            # Fuel burn (idle ships burn less)
            if ship.zone in (ShipZone.WAITING,):
                ship.fuel_criticality = min(1.0, ship.fuel_criticality + 0.001)

    # ─── Metrics ───────────────────────────────────────────────────────────

    def _update_metrics(self, events: List[SimulationEvent]):
        """Update running metrics after each tick."""
        # Queue length snapshot
        queue_len = len([s for s in self.ships if s.zone == ShipZone.WAITING])
        self.metrics["queue_length_history"].append((self.global_clock_ms, queue_len))

        # Berth utilization
        occupied = len([b for b in self.berths if b.status == "Occupied"])
        total = len(self.berths)
        self.metrics["berth_utilization_pct"] = (occupied / total * 100) if total > 0 else 0

        # Count events
        for ev in events:
            if ev.event_type == "SHIP_COMPLETED":
                self.metrics["total_ships_processed"] += 1
            elif ev.event_type in ("ENTRY_CLEARANCE", "RESHUFFLE_DENIED"):
                self.metrics["total_reshuffles"] += 1
            elif ev.event_type == "BERTH_DEADLOCK":
                self.metrics["total_deadlocks"] += 1

        # Fuel wastage estimate: sum of fuel_criticality for waiting ships
        waiting_fuel = sum(
            s.fuel_criticality for s in self.ships if s.zone == ShipZone.WAITING
        )
        self.metrics["fuel_wastage_estimate"] = round(waiting_fuel, 2)

        # Average waiting time
        waiting_ships = [s for s in self.ships if s.waiting_time_normalized > 0]
        if waiting_ships:
            avg_wait = sum(s.waiting_time_normalized for s in waiting_ships) / len(waiting_ships)
            self.metrics["avg_waiting_time_min"] = round(avg_wait * 180, 1)  # denormalize

        # Throughput
        elapsed_hours = self.global_clock_ms / 3600000
        if elapsed_hours > 0:
            self.metrics["throughput_per_hour"] = round(
                self.metrics["total_ships_processed"] / elapsed_hours, 2
            )

    def _compute_snapshot_metrics(self) -> dict:
        """Return a serializable metrics snapshot for the WebSocket payload."""
        return {
            "clock_ms": self.global_clock_ms,
            "tick": self.tick_count,
            "speed": self.playback_speed,
            "ships_processed": self.metrics["total_ships_processed"],
            "reshuffles": self.metrics["total_reshuffles"],
            "deadlocks": self.metrics["total_deadlocks"],
            "avg_wait_min": self.metrics["avg_waiting_time_min"],
            "berth_utilization_pct": self.metrics["berth_utilization_pct"],
            "fuel_wastage": self.metrics["fuel_wastage_estimate"],
            "throughput_per_hr": self.metrics["throughput_per_hour"],
            "queue_length": len([s for s in self.ships if s.zone == ShipZone.WAITING]),
        }
