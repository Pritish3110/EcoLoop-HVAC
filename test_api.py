#!/usr/bin/env python3
"""
Phase 1C: Programmatic API Verification for EnergyPlus v26.1.0
Verifies callback registration and simulation control via pyenergyplus.
"""

import os
import sys
from pyenergyplus.api import EnergyPlusAPI

def main():
    api = EnergyPlusAPI()
    state = api.state_manager.new_state()

    callback_count = 0

    def timestep_callback(state_arg):
        nonlocal callback_count
        if not api.exchange.warmup_flag(state_arg):
            year = api.exchange.year(state_arg)
            month = api.exchange.month(state_arg)
            day = api.exchange.day_of_month(state_arg)
            hour = api.exchange.hour(state_arg)
            minute = api.exchange.minutes(state_arg)
            callback_count += 1
            if callback_count % 100 == 0 or callback_count == 1:
                print(f"[API Callback #{callback_count}] Sim Time: {year:04d}-{month:02d}-{day:02d} {hour:02d}:{minute:02d}")

    # Register the callback
    api.runtime.callback_begin_system_timestep_before_predictor(state, timestep_callback)

    epw_path = os.path.expanduser("~/.local/EnergyPlus-26-1-0/WeatherData/USA_IL_Chicago-OHare.Intl.AP.725300_TMY3.epw")
    idf_path = os.path.expanduser("~/.local/EnergyPlus-26-1-0/ExampleFiles/RefBldgMediumOfficeNew2004_Chicago.idf")

    print(f"Starting EnergyPlus API simulation...")
    print(f"Weather File: {epw_path}")
    print(f"IDF File:     {idf_path}")

    # Run EnergyPlus via API
    cmd_args = ["-w", epw_path, idf_path]
    exit_code = api.runtime.run_energyplus(state, cmd_args)

    print("\n--- Simulation Summary ---")
    print(f"Exit Code: {exit_code}")
    print(f"Total Non-Warmup Timestep Callbacks Fired: {callback_count}")

    if exit_code != 0 or callback_count == 0:
        print("ERROR: Programmatic API verification failed!")
        sys.exit(1)
    else:
        print("SUCCESS: Programmatic EnergyPlus runtime control and callbacks verified!")
        sys.exit(0)

if __name__ == "__main__":
    main()
