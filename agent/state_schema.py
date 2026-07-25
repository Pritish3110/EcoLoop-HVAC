#!/usr/bin/env python3
"""
Phase 3: Sensor State Schema Definition
Defines the BuildingState data contract consumed by LLM agents in closed-loop control.
Includes rolling window statistical summaries to compress historical telemetry.
"""

from dataclasses import dataclass, field, asdict
from typing import List, Dict, Any
from collections import deque
import statistics
import json

@dataclass
class ZoneReading:
    zone_id: str
    zone_air_temp: float       # °C
    zone_comfort_proxy: float  # °C (Zone Mean Air Temperature used as comfort proxy against 20-24°C bounds)

@dataclass
class RollingStats:
    min: float
    max: float
    avg: float

@dataclass
class BuildingState:
    sim_timestamp: str                  # Format: "YYYY-MM-DD HH:MM:00" or "Day X HH:MM"
    outdoor_air_temp: float             # °C
    facility_electricity_rate: float    # kW
    facility_gas_rate: float            # kW
    zones: List[ZoneReading]            # Readings for target zones (Core_mid, Perimeter_bot_ZN_1, Perimeter_top_ZN_1)
    rolling_window: Dict[str, RollingStats] = field(default_factory=dict) # Last N intervals min/max/avg

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        d = self.to_dict()
        # Verify no null or NaN values in serialization
        dumped = json.dumps(d)
        if "NaN" in dumped or "null" in dumped or "None" in dumped:
            raise ValueError("BuildingState serialization error: detected null or NaN values!")
        return dumped

class RollingWindowTracker:
    """
    Tracks telemetry histories over a sliding window of N intervals (default N=4)
    and produces compact statistical summaries (min, max, avg).
    """
    def __init__(self, window_size: int = 4):
        self.window_size = window_size
        self.history: Dict[str, deque] = {}

    def update(self, key: str, value: float):
        if key not in self.history:
            self.history[key] = deque(maxlen=self.window_size)
        self.history[key].append(float(value))

    def get_stats(self, key: str) -> RollingStats:
        q = self.history.get(key, deque([0.0]))
        if not q:
            return RollingStats(0.0, 0.0, 0.0)
        vals = list(q)
        return RollingStats(
            min=round(min(vals), 2),
            max=round(max(vals), 2),
            avg=round(statistics.mean(vals), 2)
        )

    def get_all_stats(self) -> Dict[str, RollingStats]:
        return {key: self.get_stats(key) for key in self.history}
