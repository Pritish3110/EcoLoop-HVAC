#!/usr/bin/env python3
"""
Phase 3: Extracts Baseline KPIs (Energy, Peak Demand, and Comfort Exceedance Hours)
from models/baseline_out/eplusout.sql and saves to logs/baseline_kpis.json.
"""

import os
import sys
import json
import sqlite3
import subprocess

def run_baseline_if_needed():
    sql_path = "models/baseline_out/eplusout.sql"
    idf_path = "models/baseline.idf"
    if not os.path.exists(sql_path) or os.path.getmtime(sql_path) < os.path.getmtime(idf_path):
        print("[extract_baseline_kpis] Running baseline simulation...")
        res = subprocess.run([sys.executable, "run_baseline.py"])
        if res.returncode != 0:
            print("FATAL: run_baseline.py failed!")
            sys.exit(1)

def get_utility_kwh(conn):
    cur = conn.cursor()
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
    elec_kwh = 0.0
    gas_kwh = 0.0
    for col, val in rows:
        try:
            v = float(val)
        except ValueError:
            v = 0.0
        if col == "Electricity":
            elec_kwh = v * gj_to_kwh
        elif col == "Natural Gas":
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
            # Electricity:Facility in ReportData is in Joules per hour (J). Divide by 3,600,000 to get kW
            return round(float(res_ts[0]) / 3600000.0, 2)
    except sqlite3.Error:
        pass

    return 0.0

def get_comfort_exceedance_hours(conn, target_zones):
    cur = conn.cursor()
    # In EnergyPlus SQL, ReportDataDictionary contains variable names and KeyValues (zone names)
    # Let's check how ReportDataDictionary is structured
    cur.execute("SELECT ReportDataDictionaryIndex, KeyValue, Name, ReportingFrequency FROM ReportDataDictionary WHERE Name='Zone Mean Air Temperature' AND ReportingFrequency='Hourly';")
    rdd_rows = cur.fetchall()
    
    zone_indices = {}
    for rdd_idx, key_val, name, freq in rdd_rows:
        for z in target_zones:
            if z.lower() == key_val.lower():
                zone_indices[z] = rdd_idx

    exceedance_hours = {z: 0 for z in target_zones}
    
    # Check if Time table has Hour column
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

def main():
    run_baseline_if_needed()
    sql_path = "models/baseline_out/eplusout.sql"
    if not os.path.exists(sql_path):
        print(f"FATAL: {sql_path} does not exist!")
        sys.exit(1)

    conn = sqlite3.connect(sql_path)
    
    elec_kwh, gas_kwh = get_utility_kwh(conn)
    peak_kw = get_peak_demand_kw(conn)
    
    target_zones = ["Core_mid", "Perimeter_bot_ZN_1", "Perimeter_top_ZN_1"]
    comfort_hours = get_comfort_exceedance_hours(conn, target_zones)
    
    conn.close()

    kpis = {
        "metadata": {
            "model": "models/baseline.idf",
            "run_period": "Annual (Jan 1 - Dec 31)",
            "comfort_proxy": "Zone Mean Air Temperature outside 20.0-24.0 C during occupied hours (08:00-18:00)"
        },
        "total_facility_electricity_kwh": elec_kwh,
        "total_facility_natural_gas_kwh": gas_kwh,
        "peak_electrical_demand_kw": peak_kw,
        "comfort_exceedance_hours_occupied": comfort_hours
    }

    os.makedirs("logs", exist_ok=True)
    out_json = "logs/baseline_kpis.json"
    with open(out_json, "w") as f:
        json.dump(kpis, f, indent=2)

    print("==========================================================")
    print("Baseline KPIs Extracted & Saved to logs/baseline_kpis.json")
    print("==========================================================")
    print(json.dumps(kpis, indent=2))
    print("==========================================================")

if __name__ == "__main__":
    main()
