#!/usr/bin/env python3
"""
Phase 6: Extracts AI-Run KPIs from models/actuator_out/eplusout.sql and logs/phase6_control_log.csv,
saves to logs/ai_run_kpis.json, and computes relative comparisons against logs/baseline_kpis.json,
saving the scored evaluation results to logs/final_comparison.json.
"""

import os
import sys
import json
import csv
import sqlite3

def get_utility_kwh(conn):
    cur = conn.cursor()
    query_ts = """
    SELECT rdd.Name, SUM(rd.Value)
    FROM ReportData rd
    JOIN ReportDataDictionary rdd ON rd.ReportDataDictionaryIndex = rdd.ReportDataDictionaryIndex
    WHERE rdd.Name IN ('Electricity:Facility', 'NaturalGas:Facility', 'Gas:Facility')
      AND rdd.ReportingFrequency = 'Hourly'
    GROUP BY rdd.Name;
    """
    elec_kwh = 0.0
    gas_kwh = 0.0
    try:
        cur.execute(query_ts)
        ts_rows = cur.fetchall()
        for name, val in ts_rows:
            v = float(val) / 3600000.0  # J to kWh
            if name == 'Electricity:Facility':
                elec_kwh = v
            elif name in ('NaturalGas:Facility', 'Gas:Facility'):
                gas_kwh = v
    except sqlite3.Error as e:
        print(f"[extract_ai_run_kpis] Time-series utility error: {e}")

    # Fallback to summary table if time series was empty
    if elec_kwh == 0.0 or gas_kwh == 0.0:
        query = """
        SELECT ColumnName, Value 
        FROM TabularDataWithStrings 
        WHERE ReportName='AnnualBuildingUtilityPerformanceSummary' 
          AND TableName='End Uses'
          AND RowName='Total End Uses';
        """
        cur.execute(query)
        rows = cur.fetchall()
        gj_to_kwh = 277.77777777778
        for col, val in rows:
            try:
                v = float(val)
            except ValueError:
                v = 0.0
            if col == "Electricity" and elec_kwh == 0.0:
                elec_kwh = v * gj_to_kwh
            elif col == "Natural Gas" and gas_kwh == 0.0:
                gas_kwh = v * gj_to_kwh

    return round(elec_kwh, 2), round(gas_kwh, 2)

def get_peak_demand_kw(conn):
    cur = conn.cursor()
    query = """
    SELECT Value 
    FROM TabularDataWithStrings 
    WHERE ReportName='COMPONENTS OF PEAK ELECTRICAL DEMAND' 
      AND RowName='Maximum of Months' 
      AND ColumnName='ELECTRICITY:FACILITY {Maximum}';
    """
    cur.execute(query)
    res = cur.fetchone()
    if res and res[0]:
        try:
            val_w = float(res[0])
            return round(val_w / 1000.0, 2)
        except ValueError:
            pass

    # Fallback to time-series maximum of Electricity:Facility
    query_ts = """
    SELECT MAX(rd.Value)
    FROM ReportData rd
    JOIN ReportDataDictionary rdd ON rd.ReportDataDictionaryIndex = rdd.ReportDataDictionaryIndex
    WHERE rdd.Name = 'Electricity:Facility';
    """
    try:
        cur.execute(query_ts)
        res_ts = cur.fetchone()
        if res_ts and res_ts[0]:
            return round(float(res_ts[0]) / 3600000.0, 2)
    except sqlite3.Error:
        pass

    return 0.0

def get_comfort_exceedance_hours(conn, target_zones):
    cur = conn.cursor()
    cur.execute("SELECT ReportDataDictionaryIndex, KeyValue, Name, ReportingFrequency FROM ReportDataDictionary WHERE Name='Zone Mean Air Temperature' AND ReportingFrequency='Hourly';")
    rdd_rows = cur.fetchall()
    
    zone_indices = {}
    for rdd_idx, key_val, name, freq in rdd_rows:
        for z in target_zones:
            if z.lower() == key_val.lower():
                zone_indices[z] = rdd_idx

    exceedance_hours = {z: 0 for z in target_zones}
    
    for zone, rdd_idx in zone_indices.items():
        query_data = """
        SELECT rd.Value, t.Hour
        FROM ReportData rd
        JOIN Time t ON rd.TimeIndex = t.TimeIndex
        WHERE rd.ReportDataDictionaryIndex = ?;
        """
        cur.execute(query_data, (rdd_idx,))
        data_rows = cur.fetchall()
        for val, hr in data_rows:
            if hr is not None and 8 <= hr <= 18:
                try:
                    temp = float(val)
                    if temp < 20.0 or temp > 24.0:
                        exceedance_hours[zone] += 1
                except ValueError:
                    pass

    return exceedance_hours

def analyze_control_log(csv_path):
    if not os.path.exists(csv_path):
        return 0, 0, 0, 0.0

    total_intervals_set = set()
    total_rejections = 0
    total_escalations = 0
    latencies = []

    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            sim_time = row.get("sim_time")
            if sim_time:
                total_intervals_set.add(sim_time)
            
            # Check guardrail pass
            g_pass = str(row.get("guardrail_pass", "True")).lower() == "true"
            if not g_pass:
                total_rejections += 1
                
            # Check escalation
            esc = str(row.get("escalated", "False")).lower() == "true"
            if esc:
                total_escalations += 1
                
            # Check latency
            try:
                lat = float(row.get("llm_latency_ms", 0.0))
                if lat > 0:
                    latencies.append(lat)
            except (ValueError, TypeError):
                pass

    avg_latency = round(sum(latencies) / len(latencies), 2) if latencies else 0.0
    return len(total_intervals_set), total_rejections, total_escalations, avg_latency

def main():
    sql_path = "models/actuator_out/eplusout.sql"
    csv_path = "logs/phase6_control_log.csv"
    base_json_3day = "logs/baseline_kpis_3day.json"
    base_json_annual = "logs/baseline_kpis.json"

    if not os.path.exists(sql_path):
        print(f"FATAL: {sql_path} does not exist yet! Ensure simulation completed.")
        sys.exit(1)
    if not os.path.exists(base_json_3day):
        print(f"FATAL: {base_json_3day} does not exist! Run extract_baseline_3day_kpis.py first.")
        sys.exit(1)
    if not os.path.exists(base_json_annual):
        print(f"FATAL: {base_json_annual} does not exist!")
        sys.exit(1)

    conn = sqlite3.connect(sql_path)
    elec_kwh, gas_kwh = get_utility_kwh(conn)
    peak_kw = get_peak_demand_kw(conn)
    
    target_zones = ["Core_mid", "Perimeter_bot_ZN_1", "Perimeter_top_ZN_1"]
    comfort_hours = get_comfort_exceedance_hours(conn, target_zones)
    conn.close()

    intervals, rejections, escalations, avg_lat = analyze_control_log(csv_path)

    ai_kpis = {
        "metadata": {
            "model": "models/actuator_ready.idf",
            "run_period": "Feb 5 to Feb 7 (3 Days)",
            "comfort_proxy": "Zone Mean Air Temperature outside 20.0-24.0 C during occupied hours (08:00-18:00)"
        },
        "total_facility_electricity_kwh": elec_kwh,
        "total_facility_natural_gas_kwh": gas_kwh,
        "peak_electrical_demand_kw": peak_kw,
        "total_control_intervals_executed": intervals,
        "total_guardrail_rejections": rejections,
        "total_escalations": escalations,
        "average_llm_latency_ms": avg_lat,
        "comfort_exceedance_hours_occupied": comfort_hours
    }

    os.makedirs("logs", exist_ok=True)
    with open("logs/ai_run_kpis.json", "w") as f:
        json.dump(ai_kpis, f, indent=2)

    print("==========================================================")
    print("AI Run KPIs Extracted & Saved to logs/ai_run_kpis.json")
    print("==========================================================")
    print(json.dumps(ai_kpis, indent=2))

    # Compute Comparison against 3-Day Duration-Matched Baseline
    with open(base_json_3day, "r") as f:
        base_kpis = json.load(f)

    b_elec = base_kpis.get("total_facility_electricity_kwh", 0.01)
    b_gas = base_kpis.get("total_facility_natural_gas_kwh", 0.01)
    b_peak = base_kpis.get("peak_electrical_demand_kw", 0.01)

    elec_change_pct = round(((elec_kwh - b_elec) / b_elec) * 100.0, 2)
    gas_change_pct = round(((gas_kwh - b_gas) / b_gas) * 100.0, 2)
    peak_change_pct = round(((peak_kw - b_peak) / b_peak) * 100.0, 2)

    b_comfort = base_kpis.get("comfort_exceedance_hours_occupied", {})
    comfort_comparison = {}
    for z in target_zones:
        c_ai = comfort_hours.get(z, 0)
        c_base = b_comfort.get(z, 0)
        comfort_comparison[z] = {
            "ai_run_hours": c_ai,
            "baseline_hours": c_base,
            "difference_hours": c_ai - c_base
        }

    # Load Annual Baseline for Context
    with open(base_json_annual, "r") as f:
        base_kpis_ann = json.load(f)

    annual_reference_only = {
        "note": "WARNING: Absolute cumulative energy (kWh) is from an 8,760-hour annual run and MUST NOT be directly compared as a percentage against the 72-hour AI run.",
        "baseline_reference": "logs/baseline_kpis.json",
        "total_facility_electricity_kwh": base_kpis_ann.get("total_facility_electricity_kwh"),
        "total_facility_natural_gas_kwh": base_kpis_ann.get("total_facility_natural_gas_kwh"),
        "peak_electrical_demand_kw": base_kpis_ann.get("peak_electrical_demand_kw"),
        "comfort_exceedance_hours_occupied": base_kpis_ann.get("comfort_exceedance_hours_occupied")
    }

    comparison = {
        "metadata": {
            "evaluation_note": "Percentage change computed relative to duration-matched baseline_kpis_3day.json (negative = savings).",
            "baseline_reference": "logs/baseline_kpis_3day.json",
            "ai_run_reference": "logs/ai_run_kpis.json"
        },
        "electricity_savings": {
            "baseline_kwh": b_elec,
            "ai_run_kwh": elec_kwh,
            "percentage_change": elec_change_pct
        },
        "natural_gas_savings": {
            "baseline_kwh": b_gas,
            "ai_run_kwh": gas_kwh,
            "percentage_change": gas_change_pct
        },
        "peak_electrical_demand": {
            "baseline_kw": b_peak,
            "ai_run_kw": peak_kw,
            "percentage_change": peak_change_pct
        },
        "comfort_exceedance_hours_comparison": comfort_comparison,
        "robustness_summary": {
            "total_intervals": intervals,
            "guardrail_rejections": rejections,
            "guardrail_pass_rate_pct": round(((intervals * 3 - rejections) / (intervals * 3)) * 100.0, 2) if intervals > 0 else 0.0,
            "total_escalations": escalations,
            "average_latency_ms": avg_lat
        },
        "annual_baseline_reference_only": annual_reference_only
    }

    with open("logs/final_comparison.json", "w") as f:
        json.dump(comparison, f, indent=2)

    print("\n==========================================================")
    print("Final Scored Comparison Saved to logs/final_comparison.json")
    print("==========================================================")
    print(json.dumps(comparison, indent=2))
    print("==========================================================")

if __name__ == "__main__":
    main()
