"""
Scenario Generator — Reproducible, Parameterized Anomaly Profiles

Generates ships and injects anomalies using fixed random seeds
so that every run produces identical results for analysis.

Scenarios:
  1. Weather Cluster: ships slow down together, arrive in a congestion wave
  2. Port Congestion: all berths full, ships pile up in anchorage
  3. Emergency: tanker breakdown forces reshuffling

Each scenario returns a list of Ship objects ready for the simulation controller.
"""

import random
from typing import List, Dict, Any
from backend.models.schemas import (
    Ship, Berth, ShipZone, ShipType, CARGO_PRIORITY_MAP
)


# ─── Ship Name Generator ─────────────────────────────────────────────────────

SHIP_PREFIXES = {
    ShipType.CONTAINER: ["MV Jade", "SS Pacific", "MV Atlas", "SS Mercury", "MV Orion"],
    ShipType.BULK_CARRIER: ["MV Iron Duke", "SS Coal Runner", "MV Stone Ridge", "SS Timber"],
    ShipType.TANKER: ["MT Black Gold", "MT Sea Flame", "MT Deep Current", "MT Crude Star"],
    ShipType.ROLL_ON: ["MV Car Ferry", "MV Auto Express", "MV Wheel Runner", "MV Road King"],
    ShipType.FOOD: ["MV Fresh Harvest", "SS Cold Chain", "MV Green Cargo", "MV Fruit Express"],
}


class ScenarioGenerator:
    """
    Reproducible scenario-based ship & anomaly generator.
    Each method accepts a seed and parameters for full control.
    """

    def __init__(self, seed: int = 42):
        self.seed = seed
        self._rng = random.Random(seed)

    def _reset_rng(self, sub_seed: int = 0):
        """Reset the RNG with a combined seed for reproducibility."""
        self._rng = random.Random(self.seed + sub_seed)

    def _random_ship_type(self) -> ShipType:
        return self._rng.choice(list(ShipType))

    def _generate_ship(self, ship_id: int, ship_type: ShipType = None, **overrides) -> Ship:
        """Generate a single ship with randomized but realistic parameters."""
        st = ship_type or self._random_ship_type()
        name_pool = SHIP_PREFIXES.get(st, ["MV Unknown"])
        name = self._rng.choice(name_pool) + f" #{ship_id}"

        # Realistic size ranges by type
        size_map = {
            ShipType.CONTAINER:    {"length": (200, 400), "draft": (10, 16)},
            ShipType.BULK_CARRIER: {"length": (150, 300), "draft": (9, 14)},
            ShipType.TANKER:       {"length": (180, 350), "draft": (11, 18)},
            ShipType.ROLL_ON:      {"length": (120, 220), "draft": (6, 10)},
            ShipType.FOOD:         {"length": (100, 200), "draft": (7, 12)},
        }
        sizes = size_map.get(st, {"length": (150, 300), "draft": (8, 14)})

        ship_data = {
            "ship_id": ship_id,
            "name": name,
            "ship_type": st,
            "zone": ShipZone.OPEN_SEA,
            "length_m": self._rng.uniform(*sizes["length"]),
            "draft_m": self._rng.uniform(*sizes["draft"]),
            "speed_knots": self._rng.uniform(8, 18),
            "distance_to_boundary": self._rng.uniform(50, 200),
            "distance_to_berth": self._rng.uniform(100, 300),
            "eta_minutes": self._rng.uniform(15, 120),
            "cargo_priority": CARGO_PRIORITY_MAP.get(st, 0.2),
            "fuel_criticality": round(self._rng.uniform(0.05, 0.4), 3),
            "risk_factor": round(self._rng.uniform(0.0, 0.3), 3),
            "cargo_tons": self._rng.uniform(2000, 50000),
            "cargo_remaining_pct": 100.0,
            "estimated_processing_hours": self._rng.uniform(4, 24),
            "position_x": self._rng.uniform(0, 100),
            "position_y": self._rng.uniform(50, 550),
        }
        ship_data.update(overrides)
        return Ship(**ship_data)

    # ─── Scenario 1: Weather Cluster ─────────────────────────────────────

    def weather_cluster_scenario(
        self,
        ship_count: int = 15,
        storm_intensity: float = 0.8,
        cluster_eta_range: tuple = (5, 25),
    ) -> List[Ship]:
        """
        All ships slow down due to weather, then resume simultaneously.
        Results in a massive wave arriving at the boundary together.

        Args:
            ship_count: Number of ships in the cluster.
            storm_intensity: 0–1, affects risk_factor and speed reduction.
            cluster_eta_range: (min, max) minutes — ships arrive in this window.
        """
        self._reset_rng(sub_seed=100)
        ships = []

        for i in range(ship_count):
            speed_reduction = 1.0 - (storm_intensity * 0.6)
            ship = self._generate_ship(
                ship_id=1000 + i,
                eta_minutes=self._rng.uniform(*cluster_eta_range),
                speed_knots=self._rng.uniform(5, 12) * speed_reduction,
                risk_factor=round(storm_intensity * self._rng.uniform(0.5, 1.0), 3),
                distance_to_boundary=self._rng.uniform(10, 60),  # Already close
                zone=ShipZone.APPROACHING,
            )
            ships.append(ship)

        return ships

    # ─── Scenario 2: Port Congestion ─────────────────────────────────────

    def port_congestion_scenario(
        self,
        incoming_ships: int = 12,
        berth_count: int = 4,
        congestion_level: float = 0.9,
    ) -> tuple:
        """
        All berths are occupied, ships pile up in anchorage.
        Tests deadlock fallback and pre-assignment logic.

        Args:
            incoming_ships: Number of incoming ships.
            berth_count: Number of berths (all initially occupied).
            congestion_level: 0–1, affects how "nearly done" docked ships are.

        Returns:
            (list of incoming ships, list of berths with docked ships)
        """
        self._reset_rng(sub_seed=200)

        # Generate berths with ships already docked
        berths = []
        docked_ships = []
        for b_id in range(1, berth_count + 1):
            docked_ship = self._generate_ship(
                ship_id=2000 + b_id,
                zone=ShipZone.DOCKED,
            )
            # Ships are partially processed based on congestion level
            docked_ship.cargo_remaining_pct = (1.0 - congestion_level) * 100

            berth = Berth(
                berth_id=b_id,
                name=f"Berth {b_id}",
                status="Occupied",
                max_draft_m=self._rng.uniform(14, 20),
                length_m=self._rng.uniform(300, 450),
                equipment_types=self._rng.sample(
                    ["Cranes", "Pipes", "Ramps", "Refrigeration"],
                    k=self._rng.randint(1, 3)
                ),
                currently_docked_ship_id=docked_ship.ship_id,
                cargo_processed_pct=congestion_level * 100,
                position_x=900,
                position_y=100 + (b_id - 1) * 120,
            )
            berths.append(berth)
            docked_ships.append(docked_ship)

        # Generate incoming ships piling up outside boundary
        incoming = []
        for i in range(incoming_ships):
            ship = self._generate_ship(
                ship_id=3000 + i,
                zone=ShipZone.WAITING,
                distance_to_boundary=0.0,
            )
            incoming.append(ship)

        return docked_ships + incoming, berths

    # ─── Scenario 3: Emergency ───────────────────────────────────────────

    def emergency_scenario(
        self,
        normal_ships: int = 8,
        emergency_type: ShipType = ShipType.TANKER,
    ) -> List[Ship]:
        """
        Normal queue with a sudden emergency ship arrival.
        Tests the reshuffle threshold and priority override.

        Returns:
            Ships list with one emergency ship mixed in.
        """
        self._reset_rng(sub_seed=300)

        ships = []
        for i in range(normal_ships):
            ship = self._generate_ship(
                ship_id=4000 + i,
                zone=ShipZone.WAITING,
                distance_to_boundary=0.0,
            )
            ships.append(ship)

        # The emergency ship
        emergency = self._generate_ship(
            ship_id=9999,
            ship_type=emergency_type,
            name=f"EMERGENCY {emergency_type.value} #9999",
            zone=ShipZone.APPROACHING,
            eta_minutes=3.0,
            fuel_criticality=0.95,
            risk_factor=1.0,
            speed_knots=6.0,
            distance_to_boundary=5.0,
        )
        ships.append(emergency)

        return ships

    # ─── Mixed / Custom ─────────────────────────────────────────────────

    def generate_default_berths(self, count: int = 6) -> List[Berth]:
        """Generate a set of free berths with varied capabilities."""
        self._reset_rng(sub_seed=500)
        berths = []

        equipment_configs = [
            ["Cranes"],
            ["Cranes", "Refrigeration"],
            ["Pipes"],
            ["Ramps"],
            ["Cranes", "Pipes"],
            ["Cranes", "Ramps", "Refrigeration"],
        ]

        for i in range(count):
            eq = equipment_configs[i % len(equipment_configs)]
            berth = Berth(
                berth_id=i + 1,
                name=f"Berth {i + 1}",
                status="Free",
                max_draft_m=self._rng.uniform(12, 20),
                length_m=self._rng.uniform(250, 450),
                equipment_types=eq,
                position_x=900,
                position_y=80 + i * 100,
            )
            berths.append(berth)

        return berths

    def load_ais_playback(self, ship_count: int = 20):
        """
        Load a realistic mix of ships from MongoDB and build a playback buffer.
        Returns (ships_list, playback_buffer_dict).
        """
        self._reset_rng(sub_seed=500)
        
        try:
            from backend.models.database import raw_data_collection
        except ImportError:
            return [], {}
            
        # Find some ships that have trajectories
        # We sampled 150k rows downsampled, finding distinct mmsi is easy.
        # Just grab the first X ships
        pipeline = [
            {"$group": {"_id": "$ship_id", "count": {"$sum": 1}}},
            {"$match": {"count": {"$gte": 5}}}, # Need at least some trajectory
            {"$limit": ship_count}
        ]
        
        agg = list(raw_data_collection.aggregate(pipeline))
        mmsi_list = [d["_id"] for d in agg]
        
        if not mmsi_list:
            # Fallback
            return self.generate_default_ships(ship_count), {}
            
        ships = []
        playback_buffer = {}
        
        for i, mmsi in enumerate(mmsi_list):
            import pymongo
            cursor = raw_data_collection.find({"ship_id": mmsi}).sort("timestamp", pymongo.ASCENDING)
            traj_docs = list(cursor)
            
            if not traj_docs:
                continue
                
            first_doc = traj_docs[0]
            base_time = first_doc["timestamp"]
            
            st_raw = first_doc.get("ship_type", "Container")
            try:
                st = ShipType(st_raw)
            except:
                st = ShipType.CONTAINER
            
            # Form base ship
            ship = self._generate_ship(
                ship_id=int(mmsi) % 1000000, # Avoid overflow in js UI
                name=first_doc.get("vessel_name", f"MV {mmsi}"),
                ship_type=st,
                speed_knots=first_doc.get("speed", 10.0),
                heading_deg=first_doc.get("heading", 90.0),
                zone=ShipZone.OPEN_SEA
            )
            
            # Map longitude to position bounds (e.g. 0 to 400 X, leaving 400 for boundary)
            # Longitudes run anywhere. We just fake map it for visual scaling.
            lon = first_doc.get("lon", 0)
            lat = first_doc.get("lat", 0)
            ship.position_x = (lon % 10) * 40 # Random deterministic layout
            ship.position_y = 50 + ((lat % 10) * 50)
            
            ships.append(ship)
            
            # Build playback: array of (offset_ms, lat, lon, heading, speed)
            buffer = []
            for doc in traj_docs:
                offset_ms = int((doc["timestamp"] - base_time).total_seconds() * 1000)
                buffer.append((
                    offset_ms,
                    doc.get("lat", 0),
                    doc.get("lon", 0),
                    doc.get("heading", 0),
                    doc.get("speed", 0)
                ))
            playback_buffer[ship.ship_id] = buffer
            
        # Optional Anomaly Overlay (Weather scenario logic)
        # e.g., for weather scenario, multiply speed values in the buffer.
            
        return ships, playback_buffer
