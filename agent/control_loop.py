#!/usr/bin/env python3
"""
Phase 5: Guardrail Hardening & Extended Multi-Day Stress Test
Executes a live closed-loop control simulation where an LLM (Ollama llama3.1:8b) evaluates
building telemetry every control interval, reasons about comfort vs energy trade-offs,
and issues structured tool calls to adjust zone thermostat setpoints.
All setpoints pass through SetpointGuardrail, which enforces bounds, tracks consecutive rejections,
and triggers safe default escalation (20.0°C/24.0°C) after 3 consecutive failures.
Runs for an extended 12-hour stress horizon (36 control intervals = 108 zone decisions) in Phase 5.
"""

import os
import sys
import time
import json
import csv
import re
import urllib.request
import urllib.error
from typing import Dict, Any, List, Set, Tuple
from pyenergyplus.api import EnergyPlusAPI

from agent.state_schema import ZoneReading, RollingStats, BuildingState, RollingWindowTracker
from agent.tools import get_tools_schema
from agent.guardrails import SetpointGuardrail, VALID_ZONES
from agent.prompt_builder import generate_prompts

OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL_NAME = "llama3.1:8b"
TIMEOUT_SEC = 45.0
MAX_INTERVALS = 504  # 7 simulated days (504 control intervals = 1512 zone tool decisions) for Phase 6 robustness verification

def parse_llm_tools(message: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Parses tool calls from Ollama response, handling both native API tool_calls
    and fallback JSON code blocks in text content.
    """
    results = []
    # 1. Native tool_calls
    tcs = message.get("tool_calls", [])
    if tcs:
        for tc in tcs:
            func = tc.get("function", {})
            name = func.get("name")
            args = func.get("arguments", {})
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except Exception:
                    pass
            if name and isinstance(args, dict):
                results.append({"name": name, "arguments": args})
        if results:
            return results

    # 2. Textual content JSON fallback
    content = message.get("content", "")
    if not content:
        return []
    
    patterns = [r"```(?:json)?\s*([\s\S]*?)\s*```", r"(\[[\s\S]*\])", r"(\{[\s\S]*\})"]
    for pat in patterns:
        matches = re.findall(pat, content)
        for match in matches:
            try:
                data = json.loads(match)
                if isinstance(data, list):
                    for item in data:
                        if isinstance(item, dict):
                            name = item.get("name") or item.get("function", {}).get("name")
                            args = item.get("parameters") or item.get("arguments") or item.get("function", {}).get("arguments")
                            if name and isinstance(args, dict):
                                results.append({"name": name, "arguments": args})
                elif isinstance(data, dict):
                    name = data.get("name") or data.get("function", {}).get("name")
                    args = data.get("parameters") or data.get("arguments") or data.get("function", {}).get("arguments")
                    if name and isinstance(args, dict):
                        results.append({"name": name, "arguments": args})
                if results:
                    return results
            except Exception:
                continue
    return results

def call_ollama(prompts: List[Dict[str, str]], tools_schema: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], float, str]:
    """
    Calls Ollama REST API with tool calling schema and a hard timeout.
    Returns:
        (parsed_tool_calls_list, latency_ms, error_string)
    """
    payload = {
        "model": MODEL_NAME,
        "messages": prompts,
        "tools": tools_schema,
        "stream": False,
        "options": {
            "temperature": 0.1
        }
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(OLLAMA_URL, data=data, headers={"Content-Type": "application/json"})
    
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_SEC) as response:
            result = json.loads(response.read().decode("utf-8"))
        latency_ms = round((time.time() - t0) * 1000.0, 2)
        message = result.get("message", {})
        tool_calls = parse_llm_tools(message)
        return tool_calls, latency_ms, ""
    except urllib.error.URLError as e:
        latency_ms = round((time.time() - t0) * 1000.0, 2)
        return [], latency_ms, f"URLError: {e}"
    except Exception as e:
        latency_ms = round((time.time() - t0) * 1000.0, 2)
        return [], latency_ms, f"Exception: {e}"

def main():
    api = EnergyPlusAPI()
    state = api.state_manager.new_state()

    # Request whole-building electricity demand rate variable before simulation starts
    api.exchange.request_variable(state, "Facility Total Electricity Demand Rate", "Whole Building")

    epw_path = os.path.expanduser("~/.local/EnergyPlus-26-1-0/WeatherData/USA_IL_Chicago-OHare.Intl.AP.725300_TMY3.epw")
    idf_path = os.path.expanduser("models/actuator_ready.idf")
    log_dir = "logs"
    os.makedirs(log_dir, exist_ok=True)
    out_csv = os.path.join(log_dir, "phase6_control_log.csv")

    # Initialize CSV control log with 'escalated' column
    csv_header = [
        "sim_time", "zone", "requested_heating", "requested_cooling",
        "applied_heating", "applied_cooling", "guardrail_pass", "escalated",
        "rationale_text", "llm_latency_ms"
    ]
    with open(out_csv, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(csv_header)

    target_zones = ["Core_mid", "Perimeter_bot_ZN_1", "Perimeter_top_ZN_1"]

    var_handles: Dict[str, int] = {}
    meter_handles: Dict[str, int] = {"gas": -1}
    actuator_handles: Dict[str, Dict[str, int]] = {
        z: {"htg": -1, "clg": -1} for z in target_zones
    }

    tracker = RollingWindowTracker(window_size=4)
    guardrail = SetpointGuardrail()
    tools_schema = get_tools_schema()
    last_feedback: Dict[str, str] = {}

    timestep_count = 0
    control_interval_count = 0

    def timestep_callback(state_arg):
        nonlocal timestep_count, control_interval_count, last_feedback

        if api.exchange.warmup_flag(state_arg):
            return

        timestep_count += 1

        # 1. Acquire / re-verify variable and meter handles
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

            # Acquire EMS actuator handles for setpoint schedules
            if actuator_handles[zone]["htg"] == -1:
                h = api.exchange.get_actuator_handle(state_arg, "Schedule:Constant", "Schedule Value", f"HTGSETP_SCH_{zone}")
                if h != -1:
                    actuator_handles[zone]["htg"] = h
            if actuator_handles[zone]["clg"] == -1:
                c = api.exchange.get_actuator_handle(state_arg, "Schedule:Constant", "Schedule Value", f"CLGSETP_SCH_{zone}")
                if c != -1:
                    actuator_handles[zone]["clg"] = c

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

        # Verify handles are ready
        if "oa_temp" not in var_handles or len([k for k in var_handles if k.startswith("temp_")]) < 3:
            return

        # Check actuator readiness
        for zone in target_zones:
            if actuator_handles[zone]["htg"] == -1 or actuator_handles[zone]["clg"] == -1:
                return

        # 2. Check control interval boundary (every 2 timesteps = 20 simulation minutes with Timestep=6)
        if timestep_count % 2 != 0:
            return

        # Stop simulation if we reached the required verification duration (36 intervals = 12 simulated hours)
        if control_interval_count >= MAX_INTERVALS:
            print(f"\n[VERIFICATION COMPLETE] Reached {MAX_INTERVALS} control intervals (7 simulated days). Terminating cleanly.")
            api.runtime.stop_simulation(state_arg)
            return

        control_interval_count += 1
        year = api.exchange.year(state_arg)
        month = api.exchange.month(state_arg)
        day = api.exchange.day_of_month(state_arg)
        hour = api.exchange.hour(state_arg)
        minute = api.exchange.minutes(state_arg)
        timestamp = f"{year:04d}-{month:02d}-{day:02d} {hour:02d}:{minute:02d}:00"

        # 3. Read sensors and update rolling window tracker
        oa_val = round(api.exchange.get_variable_value(state_arg, var_handles["oa_temp"]), 2)
        
        elec_kw = 0.0
        if "elec_rate" in var_handles and var_handles["elec_rate"] != -1:
            val_w = api.exchange.get_variable_value(state_arg, var_handles["elec_rate"])
            elec_kw = round(val_w / 1000.0, 2)

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

        b_state = BuildingState(
            sim_timestamp=timestamp,
            outdoor_air_temp=oa_val,
            facility_electricity_rate=elec_kw,
            facility_gas_rate=gas_kw,
            zones=zone_readings,
            rolling_window=tracker.get_all_stats()
        )

        # 4. Synthesize prompts and invoke Ollama LLM
        prompts = generate_prompts(b_state, last_feedback)
        last_feedback.clear()  # reset feedback for this new turn

        print(f"[INTERVAL #{control_interval_count:02d}] {timestamp} | OA: {oa_val}°C | Elec: {elec_kw} kW | Invoking LLM...")
        tool_calls, latency_ms, err_str = call_ollama(prompts, tools_schema)

        zones_processed: Set[str] = set()

        if err_str != "" or not tool_calls:
            # LLM Failure or Timeout -> Record guardrail failure for all zones
            fail_reason = err_str if err_str != "" else "No tool calls returned by LLM"
            print(f"  [LLM ERROR] {fail_reason} (Latency: {latency_ms} ms). Applying fallback setpoints.")
            for zone in target_zones:
                is_val, fb, reason, esc = guardrail.validate_setpoint(zone, None, None)
                api.exchange.set_actuator_value(state_arg, actuator_handles[zone]["htg"], fb["heating"])
                api.exchange.set_actuator_value(state_arg, actuator_handles[zone]["clg"], fb["cooling"])
                last_feedback[zone] = f"LLM call failed ({fail_reason}); fallback applied."
                row = [timestamp, zone, "N/A", "N/A", fb["heating"], fb["cooling"], False, esc, f"LLM_ERROR: {fail_reason}", latency_ms]
                with open(out_csv, "a", newline="") as f:
                    csv.writer(f).writerow(row)
            return

        # 5. Process structured tool calls
        for tc in tool_calls:
            name = tc.get("name")
            args = tc.get("arguments", {})

            if name != "set_zone_setpoint" or not isinstance(args, dict):
                continue

            zone_id = args.get("zone_id")
            if zone_id not in VALID_ZONES or zone_id in zones_processed:
                continue

            req_htg = args.get("heating_setpoint_c")
            req_clg = args.get("cooling_setpoint_c")
            rationale = str(args.get("rationale", "")).strip().replace("\n", " ")

            is_valid, clean_vals, reason, escalated = guardrail.validate_setpoint(zone_id, req_htg, req_clg)
            zones_processed.add(zone_id)

            if is_valid:
                # Apply validated setpoints to actuators
                api.exchange.set_actuator_value(state_arg, actuator_handles[zone_id]["htg"], clean_vals["heating"])
                api.exchange.set_actuator_value(state_arg, actuator_handles[zone_id]["clg"], clean_vals["cooling"])
                print(f"  [{zone_id}] PASS -> Htg: {clean_vals['heating']}°C, Clg: {clean_vals['cooling']}°C | {rationale[:60]}...")
                row = [timestamp, zone_id, req_htg, req_clg, clean_vals["heating"], clean_vals["cooling"], True, escalated, rationale, latency_ms]
            else:
                # Guardrail Rejection -> Apply fallback from clean_vals
                api.exchange.set_actuator_value(state_arg, actuator_handles[zone_id]["htg"], clean_vals["heating"])
                api.exchange.set_actuator_value(state_arg, actuator_handles[zone_id]["clg"], clean_vals["cooling"])
                last_feedback[zone_id] = f"Proposed setpoints (Htg:{req_htg}, Clg:{req_clg}) REJECTED: {reason}"
                print(f"  [{zone_id}] REJECTED ({reason}) -> Fallback Htg: {clean_vals['heating']}°C, Clg: {clean_vals['cooling']}°C (Escalated: {escalated})")
                row = [timestamp, zone_id, req_htg, req_clg, clean_vals["heating"], clean_vals["cooling"], False, escalated, f"REJECTED: {reason} | Rationale: {rationale}", latency_ms]

            with open(out_csv, "a", newline="") as f:
                csv.writer(f).writerow(row)

        # 6. Check for missing zones not addressed by LLM tool calls
        for zone in target_zones:
            if zone not in zones_processed:
                is_val, fb, reason, esc = guardrail.validate_setpoint(zone, None, None)
                api.exchange.set_actuator_value(state_arg, actuator_handles[zone]["htg"], fb["heating"])
                api.exchange.set_actuator_value(state_arg, actuator_handles[zone]["clg"], fb["cooling"])
                last_feedback[zone] = "LLM omitted tool call for this zone; fallback applied."
                print(f"  [{zone}] MISSING TOOL CALL -> Fallback Htg: {fb['heating']}°C, Clg: {fb['cooling']}°C (Escalated: {esc})")
                row = [timestamp, zone, "MISSING", "MISSING", fb["heating"], fb["cooling"], False, esc, "MISSING_ZONE_TOOL_CALL", latency_ms]
                with open(out_csv, "a", newline="") as f:
                    csv.writer(f).writerow(row)

    api.runtime.callback_begin_system_timestep_before_predictor(state, timestep_callback)

    print("==========================================================")
    print("Starting Phase 6 LLM Agent Multi-Day Robustness Test (7 Days)...")
    print(f"Model: {MODEL_NAME} at {OLLAMA_URL}")
    print(f"Target Cadence: {MAX_INTERVALS} control intervals (7 simulated days)")
    print("==========================================================")

    os.makedirs("models/actuator_out", exist_ok=True)
    cmd_args = ["-d", "models/actuator_out", "-w", epw_path, idf_path]
    exit_code = api.runtime.run_energyplus(state, cmd_args)

    print("\n==========================================================")
    print("--- Phase 6 Closed-Loop Simulation Summary ---")
    print(f"Exit Code:              {exit_code}")
    print(f"Total Control Intervals: {control_interval_count}")
    print(f"Log File:               {out_csv}")
    print("==========================================================")

    if control_interval_count == 0:
        print("ERROR: No control intervals executed!")
        sys.exit(1)

    print(f"SUCCESS: Closed-loop verification run completed! Inspect {out_csv} for diagnostics.")
    sys.exit(0)

if __name__ == "__main__":
    main()
