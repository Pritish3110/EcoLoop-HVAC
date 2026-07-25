#!/usr/bin/env python3
"""
Compares total facility energy consumption between baseline and actuator override runs
by querying eplusout.sql SQLite databases.
"""

import sqlite3
import sys

def get_site_energy(sql_path):
    conn = sqlite3.connect(sql_path)
    cur = conn.cursor()
    query = """
    SELECT RowName, ColumnName, Value 
    FROM TabularDataWithStrings 
    WHERE ReportName='AnnualBuildingUtilityPerformanceSummary' 
      AND TableName='Site and Source Energy'
      AND ColumnName='Total Energy';
    """
    cur.execute(query)
    rows = cur.fetchall()
    conn.close()
    
    results = {}
    for row_name, col_name, val in rows:
        try:
            results[row_name] = float(val)
        except ValueError:
            results[row_name] = val
    return results

def get_end_uses(sql_path):
    conn = sqlite3.connect(sql_path)
    cur = conn.cursor()
    query = """
    SELECT RowName, ColumnName, Value 
    FROM TabularDataWithStrings 
    WHERE ReportName='AnnualBuildingUtilityPerformanceSummary' 
      AND TableName='End Uses'
      AND RowName='Total End Uses';
    """
    cur.execute(query)
    rows = cur.fetchall()
    conn.close()
    
    results = {}
    for row_name, col_name, val in rows:
        try:
            results[col_name] = float(val)
        except ValueError:
            results[col_name] = val
    return results

def main():
    base_sql = "models/baseline_out/eplusout.sql"
    act_sql = "models/actuator_out/eplusout.sql"

    print("==========================================================")
    print("Comparing EnergyPlus Simulation Output SQL Databases...")
    print("==========================================================")

    base_site = get_site_energy(base_sql)
    act_site = get_site_energy(act_sql)

    print("\n--- Site and Source Energy (GJ) ---")
    for k in base_site:
        b_val = base_site.get(k, 0.0)
        a_val = act_site.get(k, 0.0)
        diff = a_val - b_val
        pct = (diff / b_val * 100.0) if b_val != 0 else 0.0
        print(f"{k:<30} | Baseline: {b_val:>10.2f} | Actuator: {a_val:>10.2f} | Diff: {diff:>8.2f} ({pct:>6.2f}%)")

    base_uses = get_end_uses(base_sql)
    act_uses = get_end_uses(act_sql)

    print("\n--- Total End Uses by Fuel Type (GJ) ---")
    for k in base_uses:
        b_val = base_uses.get(k, 0.0)
        a_val = act_uses.get(k, 0.0)
        diff = a_val - b_val
        pct = (diff / b_val * 100.0) if b_val != 0 else 0.0
        print(f"{k:<30} | Baseline: {b_val:>10.2f} | Actuator: {a_val:>10.2f} | Diff: {diff:>8.2f} ({pct:>6.2f}%)")

    # Also convert Electricity and Natural Gas to kWh
    # 1 GJ = 277.77777777778 kWh
    gj_to_kwh = 277.77777777778
    print("\n--- Summary in kWh ---")
    for k in ["Electricity", "Natural Gas"]:
        b_val = base_uses.get(k, 0.0) * gj_to_kwh
        a_val = act_uses.get(k, 0.0) * gj_to_kwh
        diff = a_val - b_val
        pct = (diff / b_val * 100.0) if b_val != 0 else 0.0
        print(f"{k:<30} | Baseline: {b_val:>12.2f} kWh | Actuator: {a_val:>12.2f} kWh | Diff: {diff:>10.2f} kWh ({pct:>6.2f}%)")
    print("==========================================================")

if __name__ == "__main__":
    main()
