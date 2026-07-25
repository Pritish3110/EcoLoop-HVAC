#!/usr/bin/env python3
"""
Runs the baseline model (models/baseline.idf) without any EMS actuator overrides
and outputs results to models/baseline_out/.
"""

import os
import sys
from pyenergyplus.api import EnergyPlusAPI

def main():
    api = EnergyPlusAPI()
    state = api.state_manager.new_state()

    epw_path = os.path.expanduser("~/.local/EnergyPlus-26-1-0/WeatherData/USA_IL_Chicago-OHare.Intl.AP.725300_TMY3.epw")
    idf_path = os.path.expanduser("models/baseline.idf")
    out_dir = "models/baseline_out"
    os.makedirs(out_dir, exist_ok=True)

    print("==========================================================")
    print("Starting Baseline Simulation (No EMS Overrides)...")
    print(f"Weather File: {epw_path}")
    print(f"IDF File:     {idf_path}")
    print(f"Output Dir:   {out_dir}")
    print("==========================================================")

    cmd_args = ["-d", out_dir, "-w", epw_path, idf_path]
    exit_code = api.runtime.run_energyplus(state, cmd_args)

    print("\n==========================================================")
    print(f"Baseline Simulation Summary - Exit Code: {exit_code}")
    print("==========================================================")

    if exit_code != 0:
        print("ERROR: Baseline simulation exited with non-zero status!")
        sys.exit(1)

    print("SUCCESS: Baseline simulation completed!")
    sys.exit(0)

if __name__ == "__main__":
    main()
