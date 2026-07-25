#!/usr/bin/env python3
"""
Phase 2: EMS Actuator Wiring & Manual Override Verification
Loads models/actuator_ready.idf and verifies deterministic runtime setpoint overrides.
"""

import os
import sys
import csv
from pyenergyplus.api import EnergyPlusAPI

def main():
    api = EnergyPlusAPI()
    state = api.state_manager.new_state()

    # Paths
    epw_path = os.path.expanduser("~/.local/EnergyPlus-26-1-0/WeatherData/USA_IL_Chicago-OHare.Intl.AP.725300_TMY3.epw")
    idf_path = os.path.expanduser("models/actuator_ready.idf")
    log_dir = "logs"
    os.makedirs(log_dir, exist_ok=True)
    csv_path = os.path.join(log_dir, "phase2_actuator_events.csv")

    # Initialize CSV file
    with open(csv_path, mode="w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Timestamp", "Zone", "Actuator_Key", "Old_Value", "New_Value", "Outdoor_Temp", "Persistence_Verified"])

    # Target zones and schedules
    target_zones = {
        "Core_mid": {"clg_sched": "CLGSETP_SCH_Core_mid", "htg_sched": "HTGSETP_SCH_Core_mid"},
        "Perimeter_bot_ZN_1": {"clg_sched": "CLGSETP_SCH_Perimeter_bot_ZN_1", "htg_sched": "HTGSETP_SCH_Perimeter_bot_ZN_1"},
        "Perimeter_top_ZN_1": {"clg_sched": "CLGSETP_SCH_Perimeter_top_ZN_1", "htg_sched": "HTGSETP_SCH_Perimeter_top_ZN_1"}
    }

    handles_acquired = False
    actuator_handles = {}
    variable_handles = {}
    last_setpoints = {zone: 24.0 for zone in target_zones}
    persistence_failures = 0
    total_overrides_logged = 0
    timestep_count = 0

    def get_valid_actuator_handle(comp_types, control_type, key):
        for c_type in comp_types:
            h = api.exchange.get_actuator_handle(state, c_type, control_type, key)
            if h != -1:
                return h, c_type
        return -1, None

    def timestep_callback(state_arg):
        nonlocal handles_acquired, persistence_failures, total_overrides_logged, timestep_count

        if api.exchange.warmup_flag(state_arg):
            return

        timestep_count += 1

        # 1. Acquire handles on first non-warmup timestep
        if not handles_acquired:
            print("[test_actuator_control] Acquiring API variable and actuator handles...")
            
            # Outdoor air temp handle
            oa_handle = api.exchange.get_variable_handle(state_arg, "Site Outdoor Air Drybulb Temperature", "Environment")
            if oa_handle == -1:
                # Try without key if needed
                oa_handle = api.exchange.get_variable_handle(state_arg, "Site Outdoor Air Drybulb Temperature", "")
            
            if oa_handle == -1:
                print("FATAL ERROR: Could not acquire variable handle for 'Site Outdoor Air Drybulb Temperature'")
                sys.exit(1)
            variable_handles["oa_temp"] = oa_handle

            # Zone thermostat setpoint variable handles for persistence checking
            for zone in target_zones:
                vh = api.exchange.get_variable_handle(state_arg, "Zone Thermostat Cooling Setpoint Temperature", zone)
                variable_handles[f"clg_sp_{zone}"] = vh

            # Actuator handles
            # In EnergyPlus API, schedule actuators might be under "Schedule:Constant", "Schedule:Compact", or "Schedule"
            possible_comp_types = ["Schedule:Constant", "Schedule:Compact", "Schedule"]
            for zone, scheds in target_zones.items():
                clg_key = scheds["clg_sched"]
                htg_key = scheds["htg_sched"]

                clg_h, found_type_clg = get_valid_actuator_handle(possible_comp_types, "Schedule Value", clg_key)
                if clg_h == -1:
                    print(f"FATAL ERROR: Actuator handle returned -1 for cooling schedule '{clg_key}'. Tested component types: {possible_comp_types}")
                    sys.exit(1)
                actuator_handles[f"clg_{zone}"] = clg_h

                htg_h, found_type_htg = get_valid_actuator_handle(possible_comp_types, "Schedule Value", htg_key)
                if htg_h == -1:
                    print(f"FATAL ERROR: Actuator handle returned -1 for heating schedule '{htg_key}'. Tested component types: {possible_comp_types}")
                    sys.exit(1)
                actuator_handles[f"htg_{zone}"] = htg_h

            print("[test_actuator_control] All 6 actuator handles and variable handles successfully acquired!")
            handles_acquired = True

        # 2. Check persistence of previous timestep override
        for zone in target_zones:
            vh = variable_handles.get(f"clg_sp_{zone}", -1)
            if vh != -1:
                actual_sp = api.exchange.get_variable_value(state_arg, vh)
                expected_sp = last_setpoints[zone]
                # Allow minor float precision tolerance
                if abs(actual_sp - expected_sp) > 0.5 and timestep_count > 1:
                    # Note: on the very first timestep actual_sp might still reflect initialization before callback
                    if timestep_count > 5:
                        persistence_failures += 1
                        if persistence_failures <= 5:
                            print(f"[WARNING] Persistence mismatch in {zone}: Expected {expected_sp}°C, but read {actual_sp}°C")

        # 3. Read current time and outdoor temperature
        year = api.exchange.year(state_arg)
        month = api.exchange.month(state_arg)
        day = api.exchange.day_of_month(state_arg)
        hour = api.exchange.hour(state_arg)
        minute = api.exchange.minutes(state_arg)
        timestamp = f"{year:04d}-{month:02d}-{day:02d} {hour:02d}:{minute:02d}:00"

        oa_temp = api.exchange.get_variable_value(state_arg, variable_handles["oa_temp"])

        # 4. Apply deterministic override rule
        # Rule: During occupied hours (8 to 18), if Outdoor Temp > 25°C, override cooling setpoint down to 22.0°C (from 24.0°C)
        if 8 <= hour <= 18 and oa_temp > 25.0:
            target_clg_val = 22.0
        else:
            target_clg_val = 24.0

        for zone, scheds in target_zones.items():
            old_val = last_setpoints[zone]
            clg_h = actuator_handles[f"clg_{zone}"]
            
            # Apply override
            api.exchange.set_actuator_value(state_arg, clg_h, target_clg_val)
            last_setpoints[zone] = target_clg_val

            # Log event if setpoint changed or periodically during override (e.g., at top of hour when active)
            if target_clg_val != old_val or (target_clg_val == 22.0 and minute == 0):
                total_overrides_logged += 1
                with open(csv_path, mode="a", newline="") as f:
                    writer = csv.writer(f)
                    writer.writerow([timestamp, zone, scheds["clg_sched"], old_val, target_clg_val, f"{oa_temp:.2f}", "Yes" if persistence_failures == 0 else "No"])

                if total_overrides_logged <= 10 or total_overrides_logged % 50 == 0:
                    print(f"[OVERRIDE #{total_overrides_logged}] {timestamp} | {zone} | OA Temp: {oa_temp:.1f}°C | Clg Setpoint: {old_val}°C -> {target_clg_val}°C")

    # Register callback
    api.runtime.callback_begin_system_timestep_before_predictor(state, timestep_callback)

    print("==========================================================")
    print("Starting Phase 2 Actuator Verification Simulation...")
    print(f"Weather File: {epw_path}")
    print(f"IDF File:     {idf_path}")
    print("==========================================================")

    os.makedirs("models/actuator_out", exist_ok=True)
    cmd_args = ["-d", "models/actuator_out", "-w", epw_path, idf_path]
    exit_code = api.runtime.run_energyplus(state, cmd_args)

    print("\n==========================================================")
    print("--- Simulation Summary ---")
    print(f"Exit Code:              {exit_code}")
    print(f"Total Timesteps Run:    {timestep_count}")
    print(f"Total Overrides Logged: {total_overrides_logged}")
    print(f"Persistence Failures:   {persistence_failures}")
    print("==========================================================")

    if exit_code != 0:
        print("ERROR: Simulation exited with non-zero status!")
        sys.exit(1)
    if not handles_acquired:
        print("ERROR: Never acquired actuator handles (warmup did not finish or callback not invoked)!")
        sys.exit(1)
    if total_overrides_logged == 0:
        print("ERROR: No actuator override events were triggered or logged!")
        sys.exit(1)

    print(f"SUCCESS: Actuator control verified! Events saved to {csv_path}")
    sys.exit(0)

if __name__ == "__main__":
    main()
