"""
Berth Assigner — Turnaround Time Optimization with Deadlock Fallbacks

Assigns IN_CHANNEL ships to the best available berth, optimizing for
minimum total turnaround time rather than just nearest distance.

Evaluation factors:
  1. Physical compatibility (draft, length)
  2. Equipment compatibility (cranes, pipes, ramps, refrigeration)
  3. Estimated processing time at that berth
  4. Distance to berth (travel time component)

Edge Case Handling:
  - If no compatible berth is free → ship enters WAITING_FOR_BERTH fallback
  - If a berth is nearly free (cargo > 90% processed) → pre-assign the ship
  - Emergency override: fuel-critical ships get priority assignment
"""

from typing import List, Tuple, Optional
from backend.models.schemas import (
    Ship, Berth, ShipZone, ShipType,
    SHIP_EQUIPMENT_REQUIREMENTS, SimulationEvent
)
from backend.utils.logger import logger


# ─── Configuration ───────────────────────────────────────────────────────────

# Weight for turnaround components (tunable)
TRAVEL_TIME_WEIGHT = 0.3
PROCESSING_TIME_WEIGHT = 0.5
COMPATIBILITY_BONUS = 0.2

# Pre-assignment threshold: if a berth is > this % done, we can pre-assign
PRE_ASSIGN_THRESHOLD_PCT = 90.0

# Emergency fuel threshold
FUEL_EMERGENCY_THRESHOLD = 0.85


# ─── Core Assignment ─────────────────────────────────────────────────────────

def assign_berths(
    ships: List[Ship],
    berths: List[Berth],
    current_clock_ms: int
) -> Tuple[List[Ship], List[Berth], List[SimulationEvent]]:
    """
    Assign IN_CHANNEL ships to the best available berths.

    Priority:
      1. Fuel-critical ships get emergency assignment.
      2. Remaining ships are assigned by priority_score (highest first).

    Returns:
        Updated ships, berths, and generated events.
    """
    events: List[SimulationEvent] = []

    # Get ships needing berths (IN_CHANNEL, unassigned)
    candidates = [
        s for s in ships
        if s.zone == ShipZone.IN_CHANNEL and s.assigned_berth_id is None
    ]

    if not candidates:
        return ships, berths, events

    # Sort: fuel-critical first, then by priority score
    candidates.sort(
        key=lambda s: (s.fuel_criticality >= FUEL_EMERGENCY_THRESHOLD, s.priority_score),
        reverse=True
    )

    for ship in candidates:
        best_berth, turnaround_score, reason = _find_best_berth(ship, berths)

        if best_berth is not None:
            # Assign the ship
            ship.assigned_berth_id = best_berth.berth_id
            ship.zone = ShipZone.DOCKED
            ship.assignment_reason = reason

            best_berth.status = "Occupied"
            best_berth.currently_docked_ship_id = ship.ship_id
            best_berth.cargo_processed_pct = 0.0

            # Estimate when the berth will be free again
            processing_ms = int(ship.estimated_processing_hours * 3600 * 1000)
            best_berth.estimated_free_time_ms = current_clock_ms + processing_ms

            events.append(SimulationEvent(
                timestamp_ms=current_clock_ms,
                event_type="BERTH_ASSIGNMENT",
                ship_id=ship.ship_id,
                berth_id=best_berth.berth_id,
                details=reason,
                priority_score=ship.priority_score
            ))

            logger.info(
                f"BERTH_ASSIGNMENT: Ship {ship.ship_id} → Berth {best_berth.berth_id}",
                extra={
                    "ship_id": ship.ship_id,
                    "reason": reason,
                    "priority_score": ship.priority_score
                }
            )
        else:
            # DEADLOCK FALLBACK: No compatible berth available
            fallback_berth, fallback_reason = _try_pre_assignment(ship, berths, current_clock_ms)

            if fallback_berth is not None:
                ship.assignment_reason = fallback_reason
                # Don't dock yet — just record the intent
                events.append(SimulationEvent(
                    timestamp_ms=current_clock_ms,
                    event_type="PRE_ASSIGNMENT",
                    ship_id=ship.ship_id,
                    berth_id=fallback_berth.berth_id,
                    details=fallback_reason,
                    priority_score=ship.priority_score
                ))
                logger.info(
                    f"PRE_ASSIGNMENT: Ship {ship.ship_id} → Berth {fallback_berth.berth_id}",
                    extra={"ship_id": ship.ship_id, "reason": fallback_reason}
                )
            else:
                # True deadlock: ship must wait
                ship.assignment_reason = "No compatible berth available. Holding in channel."
                events.append(SimulationEvent(
                    timestamp_ms=current_clock_ms,
                    event_type="BERTH_DEADLOCK",
                    ship_id=ship.ship_id,
                    details=f"Ship {ship.ship_id} ({ship.ship_type.value}) cannot be assigned. "
                            f"All compatible berths occupied. Ship is holding.",
                    priority_score=ship.priority_score
                ))

                logger.warning(
                    f"DEADLOCK: Ship {ship.ship_id} has no compatible berth",
                    extra={"ship_id": ship.ship_id, "eta": ship.eta_minutes}
                )

    return ships, berths, events


# ─── Best Berth Selection ────────────────────────────────────────────────────

def _find_best_berth(
    ship: Ship,
    berths: List[Berth]
) -> Tuple[Optional[Berth], float, str]:
    """
    Find the optimal berth for a ship based on turnaround time minimization.

    Returns:
        (best_berth, turnaround_score, reason_string) or (None, 0, "") if none found.
    """
    free_berths = [b for b in berths if b.status == "Free"]

    if not free_berths:
        return None, 0.0, ""

    best: Optional[Berth] = None
    best_score = float('inf')  # Lower is better (minimizing turnaround)
    best_reason = ""

    required_equipment = SHIP_EQUIPMENT_REQUIREMENTS.get(ship.ship_type, [])

    for berth in free_berths:
        # ── Physical compatibility checks ──
        if ship.draft_m > berth.max_draft_m:
            continue  # Ship is too deep for this berth
        if ship.length_m > berth.length_m:
            continue  # Ship is too long for this berth

        # ── Equipment compatibility check ──
        has_equipment = all(eq in berth.equipment_types for eq in required_equipment)
        if not has_equipment:
            continue  # Berth lacks required equipment

        # ── Turnaround score calculation ──
        # Travel time component (proportional to distance)
        travel_component = abs(ship.position_y - berth.position_y) * TRAVEL_TIME_WEIGHT

        # Processing time component
        processing_component = ship.estimated_processing_hours * PROCESSING_TIME_WEIGHT

        # Compatibility bonus (better-equipped berths get a slight edge)
        equipment_overlap = len(set(berth.equipment_types) & set(required_equipment))
        compat_bonus = -(equipment_overlap * COMPATIBILITY_BONUS)  # Negative = better

        turnaround = travel_component + processing_component + compat_bonus

        reason_parts = []
        reason_parts.append(f"Draft OK ({ship.draft_m}m ≤ {berth.max_draft_m}m)")
        reason_parts.append(f"Length OK ({ship.length_m}m ≤ {berth.length_m}m)")
        reason_parts.append(f"Equipment match: {required_equipment}")
        reason_parts.append(f"Turnaround score: {turnaround:.2f}")

        if turnaround < best_score:
            best_score = turnaround
            best = berth
            best_reason = f"Assigned to Berth {berth.berth_id}. " + " | ".join(reason_parts)

    return best, best_score, best_reason


# ─── Deadlock Fallback: Pre-assignment ────────────────────────────────────────

def _try_pre_assignment(
    ship: Ship,
    berths: List[Berth],
    current_clock_ms: int
) -> Tuple[Optional[Berth], str]:
    """
    If all berths are occupied, check if any nearly-finished berth can be pre-assigned.
    The ship will wait for that berth to free up rather than being completely deadlocked.
    """
    required_equipment = SHIP_EQUIPMENT_REQUIREMENTS.get(ship.ship_type, [])
    best_candidate: Optional[Berth] = None
    best_free_time = float('inf')

    for berth in berths:
        if berth.status != "Occupied":
            continue

        # Check physical & equipment compatibility
        if ship.draft_m > berth.max_draft_m or ship.length_m > berth.length_m:
            continue
        if not all(eq in berth.equipment_types for eq in required_equipment):
            continue

        # Check if nearly done
        if berth.cargo_processed_pct >= PRE_ASSIGN_THRESHOLD_PCT:
            if berth.estimated_free_time_ms and berth.estimated_free_time_ms < best_free_time:
                best_free_time = berth.estimated_free_time_ms
                best_candidate = berth

    if best_candidate:
        remaining_ms = best_free_time - current_clock_ms
        remaining_min = max(0, remaining_ms / 60000)
        reason = (
            f"Pre-assigned to Berth {best_candidate.berth_id} "
            f"(currently {best_candidate.cargo_processed_pct:.0f}% done, "
            f"est. free in {remaining_min:.0f} min)"
        )
        return best_candidate, reason

    return None, ""


# ─── Berth Progress Update ───────────────────────────────────────────────────

def update_berth_progress(
    ships: List[Ship],
    berths: List[Berth],
    tick_seconds: float,
    current_clock_ms: int
) -> Tuple[List[Ship], List[Berth], List[SimulationEvent]]:
    """
    Advance cargo processing at occupied berths.
    Ships that finish processing transition to COMPLETED.
    """
    events = []

    for berth in berths:
        if berth.status != "Occupied" or berth.currently_docked_ship_id is None:
            continue

        # Find the docked ship
        docked_ship = next(
            (s for s in ships if s.ship_id == berth.currently_docked_ship_id), None
        )
        if not docked_ship:
            continue

        # Advance processing
        total_seconds = docked_ship.estimated_processing_hours * 3600
        if total_seconds > 0:
            progress_per_tick = (tick_seconds / total_seconds) * 100.0
            docked_ship.cargo_remaining_pct = max(0, docked_ship.cargo_remaining_pct - progress_per_tick)
            berth.cargo_processed_pct = 100.0 - docked_ship.cargo_remaining_pct

        # Check if complete
        if docked_ship.cargo_remaining_pct <= 0:
            docked_ship.zone = ShipZone.COMPLETED
            docked_ship.cargo_remaining_pct = 0.0

            berth.status = "Free"
            berth.currently_docked_ship_id = None
            berth.estimated_free_time_ms = None
            berth.cargo_processed_pct = 0.0

            events.append(SimulationEvent(
                timestamp_ms=current_clock_ms,
                event_type="SHIP_COMPLETED",
                ship_id=docked_ship.ship_id,
                berth_id=berth.berth_id,
                details=f"Ship {docked_ship.ship_id} completed processing at Berth {berth.berth_id}. Berth is now free."
            ))

            logger.info(
                f"SHIP_COMPLETED: Ship {docked_ship.ship_id} at Berth {berth.berth_id}",
                extra={"ship_id": docked_ship.ship_id}
            )

    return ships, berths, events
