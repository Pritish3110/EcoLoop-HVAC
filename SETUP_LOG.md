# Phase 1 Setup & Verification Log
**Project:** Eco-Loop Building Agents (Honeywell Hackathon Closed-Loop EnergyPlus + LLM Control)  
**Date:** 2026-07-25  
**Host OS:** Ubuntu 26.04 LTS (NVIDIA GeForce RTX 3060 Laptop GPU, Driver 580.173.02, CUDA 13.0)  

---

## 1. EnergyPlus Configuration
- **Version:** `v26.1.0-6f2e40d102`
- **Install Path:** `/home/pritish_3110/.local/EnergyPlus-26-1-0`
- **CLI Binary Link:** `/home/pritish_3110/.local/bin/energyplus`
- **Example IDF Used:** `/home/pritish_3110/.local/EnergyPlus-26-1-0/ExampleFiles/RefBldgMediumOfficeNew2004_Chicago.idf`
- **Weather EPW Used:** `/home/pritish_3110/.local/EnergyPlus-26-1-0/WeatherData/USA_IL_Chicago-OHare.Intl.AP.725300_TMY3.epw`

---

## 2. Python Virtual Environment (`.venv`)
- **Venv Location:** `/home/pritish_3110/Personal Files/Syllabus/Projects/honeywell_hackathon/.venv`
- **Python Version:** `Python 3.14.4`
- **`pyenergyplus` Import Method:** `.pth` file configuration via `/home/pritish_3110/Personal Files/Syllabus/Projects/honeywell_hackathon/.venv/lib/python3.14/site-packages/energyplus.pth` pointing directly to the bundled API root `/home/pritish_3110/.local/EnergyPlus-26-1-0`.

---

## 3. Ollama & LLM Tool-Calling Configuration
- **Ollama Binary:** `/usr/local/bin/ollama` (API v0.6.x compatible)
- **Model Pulled:** `llama3.1:8b` (ID: `46e0c10c039e`, 4.9 GB / 6.5 GB in VRAM)
- **GPU Confirmation:** Active offloading verified via `ollama ps`, running on **NVIDIA GeForce RTX 3060 Laptop GPU** (`27%/73% CPU/GPU` split, inference latency ~2.14 s).

---

## 4. Step-by-Step Verification Matrix

| Step | Verification Command | Status | Note |
| :--- | :--- | :---: | :--- |
| **Step 3: CLI Simulation** | `~/.local/bin/energyplus -w ~/.local/EnergyPlus-26-1-0/WeatherData/USA_IL_Chicago-OHare.Intl.AP.725300_TMY3.epw ~/.local/EnergyPlus-26-1-0/ExampleFiles/RefBldgMediumOfficeNew2004_Chicago.idf` | **PASS** | Completed without error (Run time ~2.29s); produced valid `eplusout.sql` and `eplusout.eso`. |
| **Step 4: Python API Control** | `./.venv/bin/python test_api.py` | **PASS** | Programmatically instantiated `EnergyPlusAPI`, registered `callback_begin_system_timestep_before_predictor`, fired 576 timestep callbacks, exit code 0. |
| **Step 5: LLM Tool Calling** | `./.venv/bin/python test_llm_tools.py && ollama ps` | **PASS** | Evaluated tool schema via REST API; model returned valid JSON tool call `set_temperature(zone="Conference_Room_1", value=21.5)` with 73% GPU layer offloading. |

## 5. Phase 2 Verification Matrix (EMS Actuator Wiring & Control)

| Step | Verification Command | Status | Note |
| :--- | :--- | :---: | :--- |
| **Step 1 & 2: Base Model Isolation & Inspection** | Created `models/baseline.idf` & `models/BUILDING_NOTES.md` | **PASS** | Documented 15-zone topology, shared Compact schedules, and set up isolated baseline IDF with weather file run periods enabled. |
| **Step 3: Actuator Hooks (`actuator_ready.idf`)** | Decoupled schedules for `Core_mid`, `Perimeter_bot_ZN_1`, `Perimeter_top_ZN_1` | **PASS** | Replaced shared Compact schedules with 6 dedicated `Schedule:Constant` objects and attached 6 `EnergyManagementSystem:Actuator` hooks targeting `"Schedule Value"`. |
| **Step 4: Python Override Script** | `./.venv/bin/python test_actuator_control.py` | **PASS** | Successfully acquired handles under `"Schedule:Constant"`/`"Schedule Value"`, applied OA > 25°C cooling override to 22°C, logged 606 events to `logs/phase2_actuator_events.csv`, 0 persistence failures. |
| **Step 5: Energy Impact Proof** | `./.venv/bin/python run_baseline.py && ./venv/bin/python compare_results.py` | **PASS** | Proved deterministic energy increase: **+3.67% electricity (+28,219 kWh)** and **+7.76% natural gas (+4,686 kWh)** when override rules were applied. |

---

## 6. Next Steps (Phase 3 Readiness)
All Phase 2 stop conditions (valid actuator handles, setpoint override persistence, and measurable energy delta) have been met and documented in `models/BUILDING_NOTES.md`. The environment and actuator infrastructure are verified and ready for Phase 3 (State monitoring, KPI establishment, and closed-loop data pipeline preparation).
