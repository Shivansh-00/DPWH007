"""
Queue Manager — Control-Based Entry Sequencing

This module replaces naive physical reshuffling with realistic
port-authority style entry control decisions.

Key Principles:
  - Reshuffling is only allowed while ships are in the WAITING (anchorage) zone.
  - Once a ship is CLEARED_TO_ENTER or IN_CHANNEL, its order is FIXED.
  - The system decides WHICH ship proceeds next, not where ships physically are.

Scoring Function (all inputs normalized 0–1):
  priority_score = w1*cargo_priority + w2*waiting_time + w3*ETA_urgency + w4*risk + w5*fuel

Reshuffle Threshold:
  A higher-priority ship can jump ahead of a lower-priority WAITING ship
  only if the ETA difference exceeds RESHUFFLE_THRESHOLD_MINUTES.
"""

from typing import List, Tuple, Optional
from backend.models.schemas import (
    Ship, ShipZone, ShipType, ScoringWeights,
    CARGO_PRIORITY_MAP, SimulationEvent
)
from backend.utils.logger import logger


# ─── Configuration ───────────────────────────────────────────────────────────

DEFAULT_WEIGHTS = ScoringWeights()
RESHUFFLE_THRESHOLD_MINUTES = 10.0  # Minimum ETA gap to allow entry reordering
MAX_WAITING_TIME_MINUTES = 180.0    # Normalizer: 3 hours is the "worst case" wait
MAX_ETA_MINUTES = 120.0             # Normalizer: 2 hours is max meaningful ETA


# ─── Scoring ─────────────────────────────────────────────────────────────────

def compute_priority_score(ship: Ship, weights: ScoringWeights = DEFAULT_WEIGHTS) -> float:
    """
    Compute a normalized priority score for a ship.
    All component inputs are clamped to [0, 1] before weighting.
    """
    cargo_p = CARGO_PRIORITY_MAP.get(ship.ship_type, 0.2)

    # Normalize waiting time: longer wait → higher urgency → score closer to 1
    wait_norm = min(ship.waiting_time_normalized, 1.0)

    # Normalize ETA urgency: LOWER eta → HIGHER urgency
    eta_norm = max(0.0, 1.0 - (ship.eta_minutes / MAX_ETA_MINUTES))
    eta_norm = min(eta_norm, 1.0)

    risk = min(ship.risk_factor, 1.0)
    fuel = min(ship.fuel_criticality, 1.0)

    score = (
        weights.cargo_priority * cargo_p
        + weights.waiting_time * wait_norm
        + weights.eta_urgency * eta_norm
        + weights.risk_factor * risk
        + weights.fuel_criticality * fuel
    )

    return round(score, 4)


def score_all_ships(ships: List[Ship], weights: ScoringWeights = DEFAULT_WEIGHTS) -> List[Ship]:
    """Recalculate and assign priority scores to all ships."""
    for ship in ships:
        ship.cargo_priority = CARGO_PRIORITY_MAP.get(ship.ship_type, 0.2)
        ship.priority_score = compute_priority_score(ship, weights)
    return ships


# ─── Waiting Time Update ─────────────────────────────────────────────────────

def update_waiting_times(ships: List[Ship], current_clock_ms: int) -> List[Ship]:
    """
    Update normalized waiting times for ships sitting in WAITING zone.
    Called every simulation tick.
    """
    for ship in ships:
        if ship.zone == ShipZone.WAITING and ship.waiting_since_ms is not None:
            waited_ms = current_clock_ms - ship.waiting_since_ms
            waited_minutes = waited_ms / 60000.0
            ship.waiting_time_normalized = min(waited_minutes / MAX_WAITING_TIME_MINUTES, 1.0)
    return ships


# ─── Control Entry Sequencing (the core decision) ───────────────────────────

def control_entry_sequence(
    ships: List[Ship],
    available_berth_count: int,
    current_clock_ms: int,
    weights: ScoringWeights = DEFAULT_WEIGHTS
) -> Tuple[List[Ship], List[SimulationEvent]]:
    """
    Determine which WAITING ships should be CLEARED_TO_ENTER next.

    This replaces the old reshuffle_queue() approach. Instead of moving ships
    physically, we grant entry clearance based on priority scoring.

    Rules:
      1. Only ships in WAITING zone are candidates.
      2. Ships are sorted by priority_score (descending).
      3. A higher-priority ship can jump ahead only if its ETA advantage
         over the next-lower ship exceeds the RESHUFFLE_THRESHOLD.
      4. Number of ships cleared ≤ number of available berths.
      5. Once cleared, ship zone transitions to CLEARED_TO_ENTER.

    Returns:
        Updated ships list and generated events.
    """
    events: List[SimulationEvent] = []

    # Step 1: Recalculate scores
    ships = update_waiting_times(ships, current_clock_ms)
    ships = score_all_ships(ships, weights)

    # Step 2: Identify candidates (WAITING zone only)
    waiting_ships = [s for s in ships if s.zone == ShipZone.WAITING]

    if not waiting_ships or available_berth_count <= 0:
        return ships, events

    # Step 3: Sort by priority score descending
    waiting_ships.sort(key=lambda s: s.priority_score, reverse=True)

    # Step 4: Apply reshuffle threshold check
    # We build the final clearance order respecting the threshold constraint
    clearance_order: List[Ship] = []
    for i, candidate in enumerate(waiting_ships):
        if len(clearance_order) >= available_berth_count:
            break

        # If this isn't the naturally "first" ship (by arrival), check threshold
        should_clear = True
        for other in waiting_ships:
            if other.ship_id == candidate.ship_id:
                continue
            if other.priority_score < candidate.priority_score:
                # Candidate has higher priority; check if ETA gap justifies jumping
                eta_diff = abs(other.eta_minutes - candidate.eta_minutes)
                if eta_diff < RESHUFFLE_THRESHOLD_MINUTES and other.waiting_time_normalized > candidate.waiting_time_normalized:
                    # The other ship has been waiting longer and the ETA difference is small
                    # → Don't jump ahead, respect arrival order
                    should_clear = False
                    events.append(SimulationEvent(
                        timestamp_ms=current_clock_ms,
                        event_type="RESHUFFLE_DENIED",
                        ship_id=candidate.ship_id,
                        details=(
                            f"Ship {candidate.ship_id} ({candidate.ship_type.value}) has higher priority "
                            f"(score={candidate.priority_score}) but ETA diff ({eta_diff:.1f} min) < threshold "
                            f"({RESHUFFLE_THRESHOLD_MINUTES} min). Respecting arrival order."
                        ),
                        priority_score=candidate.priority_score
                    ))
                    logger.info(f"RESHUFFLE_DENIED: Ship {candidate.ship_id} vs Ship {other.ship_id}", extra={
                        "ship_id": candidate.ship_id,
                        "other_ship_id": other.ship_id,
                        "eta_diff": eta_diff
                    })
                    break

        if should_clear:
            clearance_order.append(candidate)

    # Step 5: Grant clearance
    for ship in clearance_order:
        ship.zone = ShipZone.CLEARED_TO_ENTER
        reason = _build_clearance_reason(ship, waiting_ships)
        ship.assignment_reason = reason

        events.append(SimulationEvent(
            timestamp_ms=current_clock_ms,
            event_type="ENTRY_CLEARANCE",
            ship_id=ship.ship_id,
            details=reason,
            priority_score=ship.priority_score
        ))

        logger.info(
            f"ENTRY_CLEARANCE: Ship {ship.ship_id}",
            extra={
                "ship_id": ship.ship_id,
                "priority_score": ship.priority_score,
                "reason": reason,
                "eta": ship.eta_minutes
            }
        )

    return ships, events


# ─── Zone Transitions ────────────────────────────────────────────────────────

def transition_approaching_to_waiting(
    ships: List[Ship],
    boundary_distance: float,
    current_clock_ms: int
) -> Tuple[List[Ship], List[SimulationEvent]]:
    """
    Ships that have crossed the boundary transition from APPROACHING → WAITING.
    Their anchorage timer starts here.
    """
    events = []
    for ship in ships:
        if ship.zone == ShipZone.APPROACHING and ship.distance_to_boundary <= 0:
            ship.zone = ShipZone.WAITING
            ship.waiting_since_ms = current_clock_ms
            events.append(SimulationEvent(
                timestamp_ms=current_clock_ms,
                event_type="ZONE_TRANSITION",
                ship_id=ship.ship_id,
                details=f"Ship {ship.ship_id} ({ship.ship_type.value}) entered anchorage zone."
            ))
            logger.info(f"ZONE_TRANSITION: Ship {ship.ship_id} entered WAITING (Anchorage)")
    return ships, events


def transition_cleared_to_channel(
    ships: List[Ship],
    current_clock_ms: int
) -> Tuple[List[Ship], List[SimulationEvent]]:
    """
    Ships that have been CLEARED_TO_ENTER move into the IN_CHANNEL zone.
    Once in channel, order is FIXED — no more reshuffling.
    """
    events = []
    for ship in ships:
        if ship.zone == ShipZone.CLEARED_TO_ENTER:
            ship.zone = ShipZone.IN_CHANNEL
            events.append(SimulationEvent(
                timestamp_ms=current_clock_ms,
                event_type="ZONE_TRANSITION",
                ship_id=ship.ship_id,
                details=f"Ship {ship.ship_id} entered port channel. Order is now FIXED."
            ))
            logger.info(f"ZONE_TRANSITION: Ship {ship.ship_id} entered IN_CHANNEL")
    return ships, events


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _build_clearance_reason(ship: Ship, all_waiting: List[Ship]) -> str:
    """Build a human-readable explanation for why this ship was cleared."""
    parts = []
    if ship.cargo_priority >= 0.8:
        parts.append(f"High-urgency cargo ({ship.ship_type.value})")
    if ship.fuel_criticality >= 0.7:
        parts.append("Critical fuel level")
    if ship.risk_factor >= 0.6:
        parts.append("Elevated risk conditions")
    if ship.eta_minutes <= 10:
        parts.append("Very low ETA")
    if ship.waiting_time_normalized >= 0.5:
        parts.append("Extended waiting time")

    if not parts:
        parts.append("Standard priority clearance")

    rank = 1
    for other in sorted(all_waiting, key=lambda s: s.priority_score, reverse=True):
        if other.ship_id == ship.ship_id:
            break
        rank += 1

    return f"Rank #{rank} in queue. " + " + ".join(parts) + f" (score: {ship.priority_score})"


def get_queue_snapshot(ships: List[Ship]) -> List[dict]:
    """Return a simplified queue view for the UI / debugging."""
    waiting = [s for s in ships if s.zone in (ShipZone.WAITING, ShipZone.CLEARED_TO_ENTER)]
    waiting.sort(key=lambda s: s.priority_score, reverse=True)
    return [
        {
            "ship_id": s.ship_id,
            "type": s.ship_type.value,
            "zone": s.zone.value,
            "score": s.priority_score,
            "eta_min": s.eta_minutes,
            "waiting_min": round(s.waiting_time_normalized * MAX_WAITING_TIME_MINUTES, 1),
            "fuel": s.fuel_criticality,
        }
        for s in waiting
    ]
