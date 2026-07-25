#!/usr/bin/env python3
"""
Phase 3: Sensor State Monitoring Pipeline Verification
Runs models/actuator_ready.idf in a read-only pass (no actuator overrides),
acquires sensor and meter handles, constructs BuildingState at regular control intervals,
updates rolling window statistics (last N=4 intervals), logs JSON snapshots to logs/phase3_state_stream.log,
and saves 1 full simulated day of structured CSV trace to logs/phase3_state_trace.csv.
"""

import os
import sys
import csv
import json
from pyenergyplus.api import EnergyPlusAPI
from agent.state_schema import ZoneReading, RollingStats, BuildingState, RollingWindowTracker

def main():
    api = EnergyPlusAPI()
    state = api.state_manager.new_state()

    # Request whole-building electricity demand rate variable before simulation starts
    api.exchange.request_variable(state, "Facility Total Electricity Demand Rate", "Whole Building")

    epw_path = os.path.expanduser("~/.local/EnergyPlus-26-1-0/WeatherData/USA_IL_Chicago-OHare.Intl.AP.725300_TMY3.epw")
    idf_path = os.path.expanduser("models/actuator_ready.idf")
    log_dir = "logs"
    os.makedirs(log_dir, exist_ok=True)
    out_log_json = os.path.join(log_dir, "phase3_state_stream.log")
    out_log_csv = os.path.join(log_dir, "phase3_state_trace.csv")
    
    # Clear existing JSON stream log
    with open(out_log_json, "w") as f:
        f.write("")

    # Initialize CSV trace file with canonical reference header
    csv_header = [
        "timestamp", "outdoor_air_temp", "facility_electricity_rate_kw", "facility_gas_rate_kw",
        "temp_Core_mid", "comfort_Core_mid", "temp_Perimeter_bot_ZN_1", "comfort_Perimeter_bot_ZN_1",
        "temp_Perimeter_top_ZN_1", "comfort_Perimeter_top_ZN_1",
        "oa_temp_min", "oa_temp_max", "oa_temp_avg",
        "elec_rate_min", "elec_rate_max", "elec_rate_avg",
        "gas_rate_min", "gas_rate_max", "gas_rate_avg",
        "Core_mid_temp_min", "Core_mid_temp_max", "Core_mid_temp_avg",
        "Perimeter_bot_ZN_1_temp_min", "Perimeter_bot_ZN_1_temp_max", "Perimeter_bot_ZN_1_temp_avg",
        "Perimeter_top_ZN_1_temp_min", "Perimeter_top_ZN_1_temp_max", "Perimeter_top_ZN_1_temp_avg"
    ]
    with open(out_log_csv, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(csv_header)

    target_zones = ["Core_mid", "Perimeter_bot_ZN_1", "Perimeter_top_ZN_1"]

    var_handles = {}
    meter_handles = {"gas": -1}
    # Rolling window buffer of last 4 control intervals as required by plan.md
    tracker = RollingWindowTracker(window_size=4)

    timestep_count = 0
    logged_snapshots = 0
    # 72 control intervals = 24 hours (1 full simulated day) at 20-min control intervals
    max_csv_snapshots = 72

    def timestep_callback(state_arg):
        nonlocal timestep_count, logged_snapshots

        if api.exchange.warmup_flag(state_arg):
            return

        timestep_count += 1

        # 1. Acquire / re-verify handles (with dynamic re-attempt for meters)
        if "oa_temp" not in var_handles:
            oa_h = api.exchange.get_variable_handle(state_arg, "Site Outdoor Air Drybulb Temperature", "Environment")
            if oa_h == -1:
                oa_h = api.exchange.get_variable_handle(state_arg, "Site Outdoor Air Drybulb Temperature", "")
            if oa_h != -1:
                var_handles["oa_temp"] = oa_h

        for zone in target_zones:
            k = f"temp_{zone}"
            if k not in var_handles:
                zh = api.exchange.get_variable_handle(state_arg, "Zone Mean Air Temperature", zone)
                if zh != -1:
                    var_handles[k] = zh

        if "elec_rate" not in var_handles:
            eh = api.exchange.get_variable_handle(state_arg, "Facility Total Electricity Demand Rate", "Whole Building")
            if eh != -1:
                var_handles["elec_rate"] = eh

        if meter_handles["gas"] == -1:
            gm = api.exchange.get_meter_handle(state_arg, "NaturalGas:Facility")
            if gm == -1:
                gm = api.exchange.get_meter_handle(state_arg, "Gas:Facility")
            if gm != -1:
                meter_handles["gas"] = gm

        # Ensure core variable handles are ready
        if "oa_temp" not in var_handles or len([k for k in var_handles if k.startswith("temp_")]) < 3:
            return

        # 2. Check control interval boundary (every 2 timesteps = 20 simulation minutes with Timestep=6)
        if timestep_count % 2 != 0:
            return

        year = api.exchange.year(state_arg)
        month = api.exchange.month(state_arg)
        day = api.exchange.day_of_month(state_arg)
        hour = api.exchange.hour(state_arg)
        minute = api.exchange.minutes(state_arg)
        timestamp = f"{year:04d}-{month:02d}-{day:02d} {hour:02d}:{minute:02d}:00"

        # 3. Read sensors
        oa_val = round(api.exchange.get_variable_value(state_arg, var_handles["oa_temp"]), 2)
        
        # Electricity demand rate in W -> convert to kW
        elec_kw = 0.0
        if "elec_rate" in var_handles and var_handles["elec_rate"] != -1:
            val_w = api.exchange.get_variable_value(state_arg, var_handles["elec_rate"])
            elec_kw = round(val_w / 1000.0, 2)

        # Gas meter returns cumulative Joules for the timestep (10 minutes = 600 seconds)
        # Convert J over 600s to rate in kW: (J / 600 s) / 1000 W/kW = J / 600,000
        gas_kw = 0.0
        if meter_handles["gas"] != -1:
            val_j = api.exchange.get_meter_value(state_arg, meter_handles["gas"])
            gas_kw = round(val_j / 600000.0, 2)

        zone_readings = []
        for zone in target_zones:
            temp_val = round(api.exchange.get_variable_value(state_arg, var_handles[f"temp_{zone}"]), 2)
            zone_readings.append(ZoneReading(
                zone_id=zone,
                zone_air_temp=temp_val,
                zone_comfort_proxy=temp_val
            ))
            tracker.update(f"{zone}_temp", temp_val)

        tracker.update("outdoor_air_temp", oa_val)
        tracker.update("facility_electricity_rate", elec_kw)
        tracker.update("facility_gas_rate", gas_kw)

        # 4. Build BuildingState
        all_stats = tracker.get_all_stats()
        b_state = BuildingState(
            sim_timestamp=timestamp,
            outdoor_air_temp=oa_val,
            facility_electricity_rate=elec_kw,
            facility_gas_rate=gas_kw,
            zones=zone_readings,
            rolling_window=all_stats
        )

        # Verify sanity of rolling window stats (avg must be between min and max)
        for stat_key, st in all_stats.items():
            if not (st.min <= st.avg <= st.max):
                print(f"FATAL ERROR: Nonsensical rolling window stats for {stat_key}: min={st.min}, avg={st.avg}, max={st.max}")
                sys.exit(1)

        # 5. Serialize and log JSON
        try:
            json_str = b_state.to_json()
            with open(out_log_json, "a") as f:
                f.write(json_str + "\n")
            logged_snapshots += 1

            # Print one fully populated snapshot once rolling window buffer of N=4 is full
            if logged_snapshots == 4:
                print("\n==========================================================")
                print(f"[VERIFICATION] Fully-populated BuildingState snapshot at N=4 intervals ({timestamp}):")
                print(json.dumps(b_state.to_dict(), indent=2))
                print("==========================================================\n")
            elif logged_snapshots % 2000 == 0:
                print(f"[STATE SNAPSHOT #{logged_snapshots}] {timestamp} | OA Temp: {oa_val}°C | Elec: {elec_kw} kW | Gas: {gas_kw} kW")

            # 6. Save 1 full simulated day (first 72 snapshots) to CSV trace
            if logged_snapshots <= max_csv_snapshots:
                row = [
                    timestamp, oa_val, elec_kw, gas_kw,
                    zone_readings[0].zone_air_temp, zone_readings[0].zone_comfort_proxy,
                    zone_readings[1].zone_air_temp, zone_readings[1].zone_comfort_proxy,
                    zone_readings[2].zone_air_temp, zone_readings[2].zone_comfort_proxy,
                    all_stats["outdoor_air_temp"].min, all_stats["outdoor_air_temp"].max, all_stats["outdoor_air_temp"].avg,
                    all_stats["facility_electricity_rate"].min, all_stats["facility_electricity_rate"].max, all_stats["facility_electricity_rate"].avg,
                    all_stats["facility_gas_rate"].min, all_stats["facility_gas_rate"].max, all_stats["facility_gas_rate"].avg,
                    all_stats["Core_mid_temp"].min, all_stats["Core_mid_temp"].max, all_stats["Core_mid_temp"].avg,
                    all_stats["Perimeter_bot_ZN_1_temp"].min, all_stats["Perimeter_bot_ZN_1_temp"].max, all_stats["Perimeter_bot_ZN_1_temp"].avg,
                    all_stats["Perimeter_top_ZN_1_temp"].min, all_stats["Perimeter_top_ZN_1_temp"].max, all_stats["Perimeter_top_ZN_1_temp"].avg,
                ]
                with open(out_log_csv, "a", newline="") as f:
                    writer = csv.writer(f)
                    writer.writerow(row)
                if logged_snapshots == max_csv_snapshots:
                    print(f"[CSV TRACE] Saved 1 full simulated day (72 snapshots) to {out_log_csv}")

        except ValueError as e:
            print(f"FATAL ERROR during BuildingState serialization at {timestamp}: {e}")
            sys.exit(1)

    api.runtime.callback_begin_system_timestep_before_predictor(state, timestep_callback)

    print("==========================================================")
    print("Starting Phase 3 Sensor State Monitoring Pipeline Verification...")
    print(f"Weather File: {epw_path}")
    print(f"IDF File:     {idf_path}")
    print("==========================================================")

    os.makedirs("models/actuator_out", exist_ok=True)
    cmd_args = ["-d", "models/actuator_out", "-w", epw_path, idf_path]
    exit_code = api.runtime.run_energyplus(state, cmd_args)

    print("\n==========================================================")
    print("--- State Pipeline Simulation Summary ---")
    print(f"Exit Code:              {exit_code}")
    print(f"Total Timesteps Run:    {timestep_count}")
    print(f"Total State Snapshots:  {logged_snapshots}")
    print("==========================================================")

    if exit_code != 0:
        print("ERROR: Simulation exited with non-zero status!")
        sys.exit(1)
    if logged_snapshots == 0:
        print("ERROR: No BuildingState snapshots were generated!")
        sys.exit(1)

    print(f"SUCCESS: Sensor state monitoring pipeline verified! Snapshots saved to {out_log_json} and {out_log_csv}")
    sys.exit(0)

if __name__ == "__main__":
    main()
