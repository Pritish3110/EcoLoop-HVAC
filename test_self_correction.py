#!/usr/bin/env python3
"""
Phase 5: Controlled Self-Correction Verification Script
Forces a guardrail rejection on Turn 1, carries last_feedback into Turn 2,
and verifies that the Ollama LLM adjusts its proposed setpoints and rationale accordingly.
"""

import json
from agent.state_schema import BuildingState, ZoneReading, RollingStats
from agent.prompt_builder import generate_prompts
from agent.tools import get_tools_schema
from agent.control_loop import call_ollama

def run_self_correction_test():
    tools_schema = get_tools_schema()

    # 1. Simulate Turn 1 State
    state_turn1 = BuildingState(
        sim_timestamp="2026-01-21 10:00:00",
        outdoor_air_temp=-15.0,
        facility_electricity_rate=120.5,
        facility_gas_rate=45.0,
        zones=[
            ZoneReading("Core_mid", 21.0, 21.0),
            ZoneReading("Perimeter_bot_ZN_1", 20.5, 20.5),
            ZoneReading("Perimeter_top_ZN_1", 20.5, 20.5)
        ],
        rolling_window={
            "outdoor_air_temp": RollingStats(-16.0, -15.0, -15.5),
            "facility_electricity_rate": RollingStats(110.0, 120.5, 115.0),
            "facility_gas_rate": RollingStats(40.0, 45.0, 42.5),
            "Core_mid_temp": RollingStats(20.8, 21.0, 20.9),
            "Perimeter_bot_ZN_1_temp": RollingStats(20.2, 20.5, 20.3),
            "Perimeter_top_ZN_1_temp": RollingStats(20.2, 20.5, 20.3)
        }
    )

    print("=== TURN 1: Initial Invocation (No Feedback) ===")
    prompts_1 = generate_prompts(state_turn1, last_feedback={})
    tcs_1, lat_1, err_1 = call_ollama(prompts_1, tools_schema)

    if err_1 or not tcs_1:
        print(f"Error in Turn 1: {err_1}")
        return

    turn1_core = {}
    for tc in tcs_1:
        if tc.get("name") == "set_zone_setpoint" and tc.get("arguments", {}).get("zone_id") == "Core_mid":
            turn1_core = tc.get("arguments")
            break

    print(f"Turn 1 Core_mid Result: Htg={turn1_core.get('heating_setpoint_c')}, Clg={turn1_core.get('cooling_setpoint_c')}")
    print(f"Turn 1 Rationale: {turn1_core.get('rationale')}")

    # 2. Inject Forced Guardrail Rejection Feedback for Core_mid
    old_htg = float(turn1_core.get('heating_setpoint_c', 18.0))
    forced_feedback = {
        "Core_mid": f"Proposed setpoints (Htg:{old_htg}, Clg:{turn1_core.get('cooling_setpoint_c')}) REJECTED: Heating setpoint {old_htg}°C is too low for current winter draft conditions. You MUST increase heating_setpoint_c to at least 21.5°C in your next tool call to prevent discomfort."
    }

    print("\n=== INJECTING FORCED FEEDBACK FOR TURN 2 ===")
    print(f"Feedback: {forced_feedback['Core_mid']}")

    # 3. Simulate Turn 2 State (20 mins later)
    state_turn2 = BuildingState(
        sim_timestamp="2026-01-21 10:20:00",
        outdoor_air_temp=-15.2,
        facility_electricity_rate=121.0,
        facility_gas_rate=46.0,
        zones=[
            ZoneReading("Core_mid", 20.9, 20.9),
            ZoneReading("Perimeter_bot_ZN_1", 20.4, 20.4),
            ZoneReading("Perimeter_top_ZN_1", 20.4, 20.4)
        ],
        rolling_window={
            "outdoor_air_temp": RollingStats(-16.0, -15.0, -15.4),
            "facility_electricity_rate": RollingStats(110.0, 121.0, 116.0),
            "facility_gas_rate": RollingStats(40.0, 46.0, 43.5),
            "Core_mid_temp": RollingStats(20.8, 21.0, 20.9),
            "Perimeter_bot_ZN_1_temp": RollingStats(20.2, 20.5, 20.3),
            "Perimeter_top_ZN_1_temp": RollingStats(20.2, 20.5, 20.3)
        }
    )

    print("\n=== TURN 2: Second Invocation (With Rejection Feedback) ===")
    prompts_2 = generate_prompts(state_turn2, last_feedback=forced_feedback)
    tcs_2, lat_2, err_2 = call_ollama(prompts_2, tools_schema)

    if err_2 or not tcs_2:
        print(f"Error in Turn 2: {err_2}")
        return

    turn2_core = {}
    for tc in tcs_2:
        if tc.get("name") == "set_zone_setpoint" and tc.get("arguments", {}).get("zone_id") == "Core_mid":
            turn2_core = tc.get("arguments")
            break

    print(f"Turn 2 Core_mid Result: Htg={turn2_core.get('heating_setpoint_c')}, Clg={turn2_core.get('cooling_setpoint_c')}")
    print(f"Turn 2 Rationale: {turn2_core.get('rationale')}")

    new_htg = float(turn2_core.get('heating_setpoint_c', 0.0))
    print("\n=== SELF-CORRECTION EVALUATION ===")
    if new_htg >= 21.5 and new_htg != old_htg:
        print(f"SUCCESS: LLM successfully self-corrected! Heating adjusted from {old_htg}°C to {new_htg}°C.")
    else:
        print(f"FINDING: LLM responded with Htg={new_htg}°C (Old was {old_htg}°C). Check rationale for behavioral change.")

if __name__ == "__main__":
    run_self_correction_test()
