# State Schema Notes (`agent/state_schema.py`)
**Project:** Eco-Loop Building Agents (Honeywell Hackathon)  
**Phase:** Phase 3 — Baseline KPI Establishment & State Monitoring Pipeline  
**Date:** July 2026  

---

## 1. Architectural Purpose & Data Contract
In closed-loop building control, an LLM agent must receive a clean, structured representation of the building's current state at every decision boundary (control interval). Sending raw, multi-thousand-line time-series simulation logs or unparsed textual dumps to an LLM wastes context tokens, increases latency, and degrades reasoning quality.

The **`BuildingState`** dataclass defines the exact, immutable JSON data contract streamed from `pyenergyplus` to the AI agent during simulation runtime.

---

## 2. Field Specifications & Units

| Field Name | Data Type | Units | Description |
| :--- | :--- | :---: | :--- |
| `sim_timestamp` | `string` | N/A | Current simulation date and time (Format: `YYYY-MM-DD HH:MM:00`). |
| `outdoor_air_temp` | `float` | °C | Dry-bulb outdoor air temperature (`Site Outdoor Air Drybulb Temperature`). |
| `facility_electricity_rate` | `float` | kW | Instantaneous whole-building electrical demand rate (`Facility Total Electricity Demand Rate` or `Electricity:Facility` converted to kW). |
| `facility_gas_rate` | `float` | kW | Instantaneous whole-building natural gas heating demand rate (`Facility Total Natural Gas Demand Rate` or equivalent boiler/HVAC gas rate converted to kW). |
| `zones` | `List[ZoneReading]` | N/A | List of individual sensor snapshots for target thermal zones (`Core_mid`, `Perimeter_bot_ZN_1`, `Perimeter_top_ZN_1`). |

### `ZoneReading` Sub-Schema
| Field Name | Data Type | Units | Description |
| :--- | :--- | :---: | :--- |
| `zone_id` | `string` | N/A | Unique EnergyPlus thermal zone name. |
| `zone_air_temp` | `float` | °C | Current mean air temperature of the zone (`Zone Mean Air Temperature`). |
| `zone_comfort_proxy` | `float` | °C | Comfort evaluation metric. Uses zone air temperature evaluated against ASHRAE Standard 55 occupied comfort bounds (**20.0°C to 24.0°C**). |

---

## 3. Rolling Window Design Rationale (`RollingWindowTracker`)
To fulfill the requirement of **"handling lengthy simulation logs"** without dumping raw historical arrays into the agent's prompt, we implement a sliding statistical window over the last $N$ control intervals (default $N=4$, representing the last 1 hour of runtime at 15-minute intervals).

### Mechanics
- At each control interval, new telemetry values for global rates and zone temperatures are pushed into a bounded double-ended queue (`deque(maxlen=4)`).
- The `RollingWindowTracker` automatically computes a compact `RollingStats` summary (`min`, `max`, `avg`) for each monitored metric.
- This dictionary is attached directly to `BuildingState.rolling_window`.

### Benefits for Agentic Control
1. **Context Efficiency:** Compresses 60+ minutes of raw time-series data into 3 floating-point numbers per metric (~95% token reduction).
2. **Trend Awareness:** Allows the LLM to detect temperature drift (e.g., if `avg > min`, temperature is rising) and demand spikes without needing complex client-side time-series analysis.
3. **Robustness:** Guaranteed zero `null`, `None`, or `NaN` values during serialization, ensuring reliable JSON parsing by function-calling language models.
