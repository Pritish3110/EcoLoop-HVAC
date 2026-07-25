# Building Notes & Actuator Wiring Documentation
**Model:** `models/baseline.idf` & `models/actuator_ready.idf` (derived from `RefBldgMediumOfficeNew2004_Chicago.idf`)  
**Phase:** Phase 2 — EMS Actuator Wiring & Manual Override Verification  
**Date:** July 2026  

---

## 1. Thermal Zone Topology
The medium office reference building model consists of **15 thermal zones** distributed across 3 floors (Bottom, Middle, Top). Each floor has 4 perimeter zones (North, East, South, West) and 1 interior core zone:
- **Bottom Floor:** `Core_bottom`, `Perimeter_bot_ZN_1`, `Perimeter_bot_ZN_2`, `Perimeter_bot_ZN_3`, `Perimeter_bot_ZN_4`
- **Middle Floor:** `Core_mid`, `Perimeter_mid_ZN_1`, `Perimeter_mid_ZN_2`, `Perimeter_mid_ZN_3`, `Perimeter_mid_ZN_4`
- **Top Floor:** `Core_top`, `Perimeter_top_ZN_1`, `Perimeter_top_ZN_2`, `Perimeter_top_ZN_3`, `Perimeter_top_ZN_4`

---

## 2. Thermostat Control Architecture & Decoupling Strategy
Every thermal zone is controlled via a `ZoneControl:Thermostat` object coupled to a `ThermostatSetpoint:DualSetpoint` object. Notice that in the baseline model (`models/baseline.idf`), **all 15 zones share the exact same heating and cooling setpoint schedules**:
- **Heating Schedule (`HTGSETP_SCH`):** Defined as a `Schedule:Compact` object.
  - Occupied setpoint (06:00 to 22:00 on Weekdays/Saturday): **21.0°C**
  - Unoccupied setback / All other times: **15.6°C**
- **Cooling Schedule (`CLGSETP_SCH`):** Defined as a `Schedule:Compact` object.
  - Occupied setpoint (06:00 to 22:00 on Weekdays, 06:00 to 18:00 on Saturday): **24.0°C**
  - Unoccupied setback / All other times: **26.7°C**

### Surgical Decoupling for EMS Actuation
To prove surgical runtime control without globally altering all 15 zones simultaneously, we selected three representative zones spanning both core and perimeter layouts:
1. `Core_mid` (Middle floor interior core zone)
2. `Perimeter_bot_ZN_1` (Bottom floor perimeter zone 1)
3. `Perimeter_top_ZN_1` (Top floor perimeter zone 1)

In `models/actuator_ready.idf`, we modified the `ThermostatSetpoint:DualSetpoint` objects for these three zones to point to dedicated zone-specific setpoint schedules:
- `CLGSETP_SCH_Core_mid` & `HTGSETP_SCH_Core_mid`
- `CLGSETP_SCH_Perimeter_bot_ZN_1` & `HTGSETP_SCH_Perimeter_bot_ZN_1`
- `CLGSETP_SCH_Perimeter_top_ZN_1` & `HTGSETP_SCH_Perimeter_top_ZN_1`

---

## 3. EMS Actuator Configuration & Schedule Types
In `models/actuator_ready.idf`, we defined 6 dedicated `Schedule:Constant` objects (occupied baselines: 24.0°C cooling, 21.0°C heating) and attached 6 corresponding `EnergyManagementSystem:Actuator` objects targeting their `"Schedule Value"`:

| Actuator Name | Actuated Component Unique Name | Actuated Component Type | Control Type |
| :--- | :--- | :--- | :--- |
| `Actuator_Clg_Core_mid` | `CLGSETP_SCH_Core_mid` | `Schedule:Constant` | `Schedule Value` |
| `Actuator_Htg_Core_mid` | `HTGSETP_SCH_Core_mid` | `Schedule:Constant` | `Schedule Value` |
| `Actuator_Clg_Perimeter_bot_ZN_1` | `CLGSETP_SCH_Perimeter_bot_ZN_1` | `Schedule:Constant` | `Schedule Value` |
| `Actuator_Htg_Perimeter_bot_ZN_1` | `HTGSETP_SCH_Perimeter_bot_ZN_1` | `Schedule:Constant` | `Schedule Value` |
| `Actuator_Clg_Perimeter_top_ZN_1` | `CLGSETP_SCH_Perimeter_top_ZN_1` | `Schedule:Constant` | `Schedule Value` |
| `Actuator_Htg_Perimeter_top_ZN_1` | `HTGSETP_SCH_Perimeter_top_ZN_1` | `Schedule:Constant` | `Schedule Value` |

### Schedule Type Findings in EnergyPlus v26.1.0
- When acquiring actuator handles via `api.exchange.get_actuator_handle()`, we tested component types `"Schedule:Constant"`, `"Schedule:Compact"`, and `"Schedule"`.
- In EnergyPlus v26.1.0, when an actuator is defined in the IDF with Actuated Component Type `Schedule:Constant`, the Python API successfully recognizes the handle under **`"Schedule:Constant"`** with Control Type **`"Schedule Value"`**.
- Using `Schedule:Constant` for target zones rather than `Schedule:Compact` provides a clean, deterministic 24/7 baseline occupied setpoint that does not conflict with native scheduled setback transitions at midnight or weekends, making programmatic override verification unambiguous.

---

## 4. Quantitative Proof of Impact (Baseline vs. Override)
We executed an annual simulation comparison between `models/baseline.idf` (native schedules, no overrides) and `models/actuator_ready.idf` driven by `test_actuator_control.py`.

### Override Rule Applied
During occupied hours (08:00 to 18:00), whenever outdoor air temperature (`Site Outdoor Air Drybulb Temperature`) exceeded **25.0°C**, the cooling setpoints for `Core_mid`, `Perimeter_bot_ZN_1`, and `Perimeter_top_ZN_1` were programmatically overridden from 24.0°C down to **22.0°C** via `api.exchange.set_actuator_value()`.

### Simulation Results Summary
- **Total Timesteps Simulated:** 53,136 (Annual run at 6 timesteps/hour + sizing periods)
- **Total Override Events Triggered & Logged:** 606 events saved to `logs/phase2_actuator_events.csv`
- **Persistence Failures:** 0 (Confirmed via next-timestep readback of `Zone Thermostat Cooling Setpoint Temperature`)

### Annual Utility Consumption Comparison Table
| Utility / End Use | Baseline (No Overrides) | Actuator Override Run | Absolute Difference | % Difference |
| :--- | :---: | :---: | :---: | :---: |
| **Electricity (Total Facility)** | 767,958.33 kWh | 796,177.78 kWh | **+28,219.44 kWh** | **+3.67%** |
| **Natural Gas (Total Facility)** | 60,361.11 kWh | 65,047.22 kWh | **+4,686.11 kWh** | **+7.76%** |
| **Total Site Energy** | 2,981.95 GJ | 3,100.41 GJ | **+118.46 GJ** | **+3.97%** |
| **Total Source Energy** | 10,040.75 GJ | 10,419.40 GJ | **+378.65 GJ** | **+3.77%** |

### Architectural Conclusion
The measurable increase in total facility electricity (+3.67%) and natural gas reheat (+7.76%) confirms that Python-driven EMS schedule actuators deterministically alter HVAC system sizing and runtime load in EnergyPlus v26.1.0 without internal clobbering. Phase 2 actuator control is fully proven and ready for Phase 3 state monitoring and closed-loop integration.

---

## 5. Phase 3 Verification (Baseline KPIs & State Monitoring Pipeline)

### 5.1 True Ground-Truth Baseline KPIs (`logs/baseline_kpis.json`)
Using `extract_baseline_kpis.py`, we programmatically extracted the annual baseline performance metrics from the simulation SQLite database (`eplusout.sql`). These figures serve as the immutable comparison target for Phase 4+ closed-loop evaluation:
- **Facility Total Electricity:** `767,958.33 kWh`
- **Facility Total Natural Gas:** `60,361.11 kWh`
- **Peak Electrical Demand:** `344.93 kW` (derived from tabular peak components report).
- **Zone Comfort Exceedance:** Captured annual unmet cooling/heating hours across all 15 zones (e.g., `Core_mid`: 452.5 unset cooling hours, 107.0 unset heating hours).

### 5.2 Comfort Metric Rationale (ASHRAE PMV vs. Operative Temperature Proxy)
In EnergyPlus v26.1.0 with `RefBldgMediumOfficeNew2004_Chicago.idf`, Fanger PMV (`FangerPMV`) is not enabled as a standard output variable by default. To preserve minimal dependency and avoid intrusive IDF schema modifications, we utilize **Zone Mean Air Temperature** evaluated against ASHRAE Standard 55 occupied comfort bounds (**20.0°C to 24.0°C**) as our documented `zone_comfort_proxy` (per `plan.md` instructions).

### 5.3 State Pipeline & Rolling Window Verification (`test_state_pipeline.py`)
We executed an annual read-only observational pass over `models/actuator_ready.idf` without triggering actuator overrides or LLM API calls:
- **Rolling Window Buffer ($N=4$):** Maintained a sliding statistical window of the last 4 control intervals ($W=4$), computing real-time `min`, `max`, and `avg` summaries per field to compress prompt context overhead while preserving critical trend visibility.
- **Reliability Proof:** Streamed **26,568 JSON snapshots** to `logs/phase3_state_stream.log` across 53,136 simulation timesteps with **zero invalid/negative variable handles** and zero NaN/null values.
- **Reference Trace:** Saved 1 full simulated day (72 control intervals representing 24 hours of runtime) in tabular CSV format to `logs/phase3_state_trace.csv` as the canonical reference format for Phase 4 prompt builders.

---

## 6. Phase 4 Verification (LLM Agent Decision Loop & Closed-Loop Control)

### 6.1 Closed-Loop Architecture
In Phase 4, we closed the control loop by replacing static schedule overrides with live AI decision-making:
- **Control Cadence:** Every 2 simulation timesteps (20 simulation minutes), aligning with the $N=4$ rolling statistical window.
- **Defensive Guardrails:** Implemented `SetpointGuardrail` in `agent/guardrails.py` enforcing $18.0^\circ\text{C} \le T_{\text{heat}} \le 22.0^\circ\text{C}$, $23.0^\circ\text{C} \le T_{\text{cool}} \le 27.0^\circ\text{C}$, and a minimum $1.0^\circ\text{C}$ deadband ($T_{\text{cool}} - T_{\text{heat}} \ge 1.0$). Any rejection triggers an automatic fallback to the last known-good setpoint and injects self-correction feedback into the next interval's prompt.

### 6.2 Empirical Results & Reasoning Verification
- **Verification Run:** Successfully executed a continuous multi-hour verification pass logging 33 distinct zone control decisions to `logs/phase4_control_log.csv`.
- **Safety & Robustness:** Achieved a **100% guardrail pass rate** (0 out-of-bounds leaks) and **0% LLM failure rate** via our dual-mode JSON tool-call parser and 45-second timeout budget.
- **Full Documentation:** Detailed architectural rationale, latency analytics (~26.3s per 3-zone evaluation), and empirical reasoning strings are documented in `agent/PHASE4_NOTES.md`.


