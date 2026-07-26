#!/usr/bin/env python3
"""
Extracts 3-Day Baseline KPIs (Energy, Peak Demand, and Comfort Exceedance Hours)
from models/baseline_3day_out/eplusout.sql and saves to logs/baseline_kpis_3day.json.
"""

import os
import sys
import json
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
        print(f"[extract_baseline_3day_kpis] Time-series utility error: {e}")

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
            if val_w > 0:
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

def main():
    sql_path = "models/baseline_3day_out/eplusout.sql"
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
            "model": "models/baseline_3day.idf",
            "run_period": "Feb 5 to Feb 7 (3 Days / 72 Hours)",
            "comfort_proxy": "Zone Mean Air Temperature outside 20.0-24.0 C during occupied hours (08:00-18:00)"
        },
        "total_facility_electricity_kwh": elec_kwh,
        "total_facility_natural_gas_kwh": gas_kwh,
        "peak_electrical_demand_kw": peak_kw,
        "comfort_exceedance_hours_occupied": comfort_hours
    }

    os.makedirs("logs", exist_ok=True)
    out_json = "logs/baseline_kpis_3day.json"
    with open(out_json, "w") as f:
        json.dump(kpis, f, indent=2)

    print("================================================================")
    print("3-Day Baseline KPIs Extracted & Saved to logs/baseline_kpis_3day.json")
    print("================================================================")
    print(json.dumps(kpis, indent=2))
    print("================================================================")

if __name__ == "__main__":
    main()
