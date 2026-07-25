PHASE 2 — EMS ACTUATOR WIRING & MANUAL OVERRIDE VERIFICATION
Project: Eco-Loop Building Agents (Honeywell hackathon closed-loop EnergyPlus + LLM control)

CONTEXT — CARRY THESE EXACT PATHS FORWARD, DO NOT RE-DISCOVER THEM
- EnergyPlus: v26.1.0-6f2e40d102, installed at /home/pritish_3110/.local/EnergyPlus-26-1-0
- CLI binary: /home/pritish_3110/.local/bin/energyplus
- Base building: /home/pritish_3110/.local/EnergyPlus-26-1-0/ExampleFiles/RefBldgMediumOfficeNew2004_Chicago.idf
- Weather file: /home/pritish_3110/.local/EnergyPlus-26-1-0/WeatherData/USA_IL_Chicago-OHare.Intl.AP.725300_TMY3.epw
- Project venv: /home/pritish_3110/Personal Files/Syllabus/Projects/honeywell_hackathon/.venv (Python 3.14.4)
- pyenergyplus already importable via the .pth file already configured — do not touch that setup.
- Phase 1 confirmed callback_begin_system_timestep_before_predictor fires correctly (576 calls/day run).

GOAL OF THIS PHASE
Prove that a Python-driven actuator override can change this specific building's heating/cooling
setpoints at runtime, and that doing so measurably changes energy consumption in the output —
BEFORE any LLM is involved. This is the highest-risk phase in the whole project: if actuator
control doesn't provably work here, the entire closed loop is impossible. Isolate this from LLM
complexity entirely.

STEP-BY-STEP INSTRUCTIONS

1. Copy the base IDF, don't modify the original
   - Copy RefBldgMediumOfficeNew2004_Chicago.idf into the project directory as
     `models/baseline.idf`. Never edit the original ExampleFiles copy.

2. Inspect the IDF's existing thermostat control objects
   - Open baseline.idf and identify how zone thermostats are currently controlled — look for
     `ThermostatSetpoint:DualSetpoint`, `ZoneControl:Thermostat`, and the `Schedule:Compact` (or
     `Schedule:Constant`) objects driving heating/cooling setpoint schedules.
   - Document in a new `models/BUILDING_NOTES.md`: how many zones exist, which schedule objects
     drive heating/cooling setpoints, and their current setpoint values/ranges.

3. Add EMS actuator hooks
   - In baseline.idf, for at least 2–3 representative zones (not all — pick a mix of perimeter
     and core zones so results are meaningful, e.g. one perimeter office zone + the core zone),
     add `EnergyManagementSystem:Actuator` objects targeting the heating and cooling setpoint
     schedules for those zones (actuator type: Schedule Value, on the relevant
     Schedule:Compact/Constant objects identified in step 2).
   - If the existing setpoint schedules are `Schedule:Compact` (which can't be EMS-actuated
     directly in older EnergyPlus versions), replace those specific zones' setpoint schedules
     with `Schedule:Constant` objects first, then actuate those — check what's required for the
     installed v26.1.0 and document which approach was needed in BUILDING_NOTES.md.
   - Save this modified file as `models/actuator_ready.idf`.

4. Write test_actuator_control.py
   - Using the EnergyPlusAPI (same pattern verified in Phase 1's test_api.py), write a script
     that runs actuator_ready.idf against the same weather file, and inside the timestep
     callback:
     a. Gets the actuator handles for the heating/cooling setpoints on the target zones
        (via api.exchange.get_actuator_handle — confirm handles are non-negative/valid before
        proceeding, and hard-fail with a clear message if any handle is invalid).
     b. On a simple hardcoded rule (NOT an LLM yet) — e.g. "if outdoor air temp > 25°C, raise
        cooling setpoint by 2°C in the core zone" — calls set_actuator_value to override the
        setpoint.
     c. Logs every override event (sim time, zone, old value, new value) to a CSV
        `logs/phase2_actuator_events.csv`.
   - Run this end to end. Confirm:
     - No crash, full simulation completes
     - The CSV shows override events actually happened
     - Reading back the zone's setpoint via get_variable_value after the override reflects the
       new value, not the original schedule value

5. Prove it actually changes energy use
   - Run baseline.idf (unmodified, step 1 copy, no actuator overrides) through the plain
     EnergyPlus CLI and extract total facility energy from eplusout.sql.
   - Run actuator_ready.idf with the hardcoded override rule from step 4 the same way.
   - Compare total facility kWh between the two runs. They must differ — if the numbers are
     identical, the actuator override did nothing and this phase has NOT succeeded; debug
     before proceeding, do not move to Phase 3.

6. Update BUILDING_NOTES.md with final results
   - Zone list and which zones got EMS actuators
   - Actuator handle names/types used
   - Baseline kWh vs override-run kWh, and the % difference
   - Any EnergyPlus v26.1 quirks encountered (e.g. Schedule:Compact vs Schedule:Constant issue)

STOP CONDITIONS — report back rather than improvising past these:
- Any actuator handle comes back invalid (-1 or equivalent)
- Setpoint override doesn't persist / gets overwritten each timestep by the original schedule
- Baseline and override-run energy totals are identical

Do not integrate the LLM or Ollama in this phase. This phase proves manual, deterministic
actuator control works — Phase 3 establishes the real baseline KPIs, Phase 4 replaces the
hardcoded rule with the LLM decision.