#!/usr/bin/env python3
"""
Runs a 3-day duration-matched baseline simulation (Feb 5 - Feb 7, 72 hours)
on the unmodified schedule baseline model (models/baseline.idf) without EMS overrides.
Saves the modified IDF to models/baseline_3day.idf and outputs results to models/baseline_3day_out/.
"""

import os
import sys
import time
from pyenergyplus.api import EnergyPlusAPI

def create_3day_baseline_idf():
    src_path = "models/baseline.idf"
    dst_path = "models/baseline_3day.idf"
    
    with open(src_path, "r", encoding="utf-8", errors="ignore") as f:
        content = f.read()

    # 1. Disable Sizing Periods Simulation
    old_sim_control = """  SimulationControl,
    YES,                     !- Do Zone Sizing Calculation
    YES,                     !- Do System Sizing Calculation
    YES,                     !- Do Plant Sizing Calculation
    YES,                     !- Run Simulation for Sizing Periods
    YES,                     !- Run Simulation for Weather File Run Periods
    No,                      !- Do HVAC Sizing Simulation for Sizing Periods
    1;                       !- Maximum Number of HVAC Sizing Simulation Passes"""

    new_sim_control = """  SimulationControl,
    YES,                     !- Do Zone Sizing Calculation
    YES,                     !- Do System Sizing Calculation
    YES,                     !- Do Plant Sizing Calculation
    No,                      !- Run Simulation for Sizing Periods
    YES,                     !- Run Simulation for Weather File Run Periods
    No,                      !- Do HVAC Sizing Simulation for Sizing Periods
    1;                       !- Maximum Number of HVAC Sizing Simulation Passes"""

    if old_sim_control in content:
        content = content.replace(old_sim_control, new_sim_control)
        print("[run_baseline_3day] Successfully disabled Sizing Periods in SimulationControl.")
    else:
        print("[run_baseline_3day] WARNING: Could not exact-match SimulationControl block. Attempting fallback replace...")
        content = content.replace("YES,                     !- Run Simulation for Sizing Periods",
                                  "No,                      !- Run Simulation for Sizing Periods")

    # 2. Set RunPeriod to Feb 5 - Feb 7
    old_run_period = """  RunPeriod,
    annual,                  !- Name
    1,                       !- Begin Month
    1,                       !- Begin Day of Month
    ,                        !- Begin Year
    12,                      !- End Month
    31,                      !- End Day of Month
    ,                        !- End Year
    Sunday,                  !- Day of Week for Start Day
    No,                      !- Use Weather File Holidays and Special Days
    No,                      !- Use Weather File Daylight Saving Period
    No,                      !- Apply Weekend Holiday Rule
    Yes,                     !- Use Weather File Rain Indicators
    Yes;                     !- Use Weather File Snow Indicators"""

    new_run_period = """  RunPeriod,
    Feb5to7,                 !- Name
    2,                       !- Begin Month
    5,                       !- Begin Day of Month
    ,                        !- Begin Year
    2,                       !- End Month
    7,                       !- End Day of Month
    ,                        !- End Year
    Sunday,                  !- Day of Week for Start Day
    No,                      !- Use Weather File Holidays and Special Days
    No,                      !- Use Weather File Daylight Saving Period
    No,                      !- Apply Weekend Holiday Rule
    Yes,                     !- Use Weather File Rain Indicators
    Yes;                     !- Use Weather File Snow Indicators"""

    if old_run_period in content:
        content = content.replace(old_run_period, new_run_period)
        print("[run_baseline_3day] Successfully updated RunPeriod to Feb 5 - Feb 7 (3 Days).")
    else:
        print("[run_baseline_3day] FATAL: Could not exact-match RunPeriod block in models/baseline.idf!")
        sys.exit(1)

    with open(dst_path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"[run_baseline_3day] Saved duration-matched baseline IDF to {dst_path}")
    return dst_path

def main():
    idf_path = create_3day_baseline_idf()
    api = EnergyPlusAPI()
    state = api.state_manager.new_state()

    epw_path = os.path.expanduser("~/.local/EnergyPlus-26-1-0/WeatherData/USA_IL_Chicago-OHare.Intl.AP.725300_TMY3.epw")
    out_dir = "models/baseline_3day_out"
    os.makedirs(out_dir, exist_ok=True)

    print("==========================================================")
    print("Starting 3-Day Baseline Simulation (No EMS Overrides)...")
    print(f"Weather File: {epw_path}")
    print(f"IDF File:     {idf_path}")
    print(f"Output Dir:   {out_dir}")
    print("==========================================================")

    start_time = time.time()
    cmd_args = ["-d", out_dir, "-w", epw_path, idf_path]
    exit_code = api.runtime.run_energyplus(state, cmd_args)
    duration = time.time() - start_time

    print("\n==========================================================")
    print(f"3-Day Baseline Simulation Summary - Exit Code: {exit_code}")
    print(f"Execution Time: {duration:.2f} seconds")
    print("==========================================================")

    if exit_code != 0:
        print("ERROR: 3-Day Baseline simulation exited with non-zero status!")
        sys.exit(1)

    # Check eplusout.err to confirm sizing periods were genuinely skipped
    err_path = os.path.join(out_dir, "eplusout.err")
    if os.path.exists(err_path):
        with open(err_path, "r", encoding="utf-8", errors="ignore") as f:
            err_content = f.read()
            print("\n--- eplusout.err Verification ---")
            for line in err_content.splitlines():
                if "Sizing" in line or "Warmup" in line or "Run Period" in line or "Elapsed Time" in line:
                    print("  ", line)
            print("---------------------------------")

    print("SUCCESS: 3-Day duration-matched baseline simulation completed!")
    sys.exit(0)

if __name__ == "__main__":
    main()
