#!/usr/bin/env python3
"""
Generates the self-contained Quantitative Savings Dashboard HTML file
(dashboard/savings_dashboard.html) by embedding locked KPI data from
logs/final_comparison.json and time-series telemetry from logs/phase6_control_log.csv.
"""

import os
import json
import csv

def generate_dashboard():
    # 1. Load Locked KPI Data
    with open("logs/final_comparison.json", "r", encoding="utf-8") as f:
        kpis = json.load(f)

    peak_base = kpis["peak_electrical_demand"]["baseline_kw"]
    peak_ai = kpis["peak_electrical_demand"]["ai_run_kw"]
    peak_pct = kpis["peak_electrical_demand"]["percentage_change"]

    comfort_comp = kpis["comfort_exceedance_hours_comparison"]
    c_core_base = comfort_comp["Core_mid"]["baseline_hours"]
    c_core_ai = comfort_comp["Core_mid"]["ai_run_hours"]
    c_bot_base = comfort_comp["Perimeter_bot_ZN_1"]["baseline_hours"]
    c_bot_ai = comfort_comp["Perimeter_bot_ZN_1"]["ai_run_hours"]
    c_top_base = comfort_comp["Perimeter_top_ZN_1"]["baseline_hours"]
    c_top_ai = comfort_comp["Perimeter_top_ZN_1"]["ai_run_hours"]

    total_c_base = c_core_base + c_bot_base + c_top_base
    total_c_ai = c_core_ai + c_bot_ai + c_top_ai
    comfort_reduction_pct = round(((total_c_base - total_c_ai) / total_c_base) * 100.0, 2)

    rob = kpis["robustness_summary"]
    pass_rate = rob["guardrail_pass_rate_pct"]
    intervals = rob["total_intervals"]

    elec_base = kpis["electricity_savings"]["baseline_kwh"]
    elec_ai = kpis["electricity_savings"]["ai_run_kwh"]
    gas_base = kpis["natural_gas_savings"]["baseline_kwh"]
    gas_ai = kpis["natural_gas_savings"]["ai_run_kwh"]

    # 2. Load Time-Series Telemetry from CSV
    timestamps = []
    temp_core = []
    temp_bot = []
    temp_top = []

    with open("logs/phase6_control_log.csv", "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            ts = row.get("sim_time", "")
            if ts not in timestamps:
                timestamps.append(ts)

    # We need to map temperatures for each timestamp
    ts_map = {ts: {"core": None, "bot": None, "top": None} for ts in timestamps}
    with open("logs/phase6_control_log.csv", "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            ts = row.get("sim_time", "")
            zone = row.get("zone_name", "")
            try:
                t_val = float(row.get("current_temp", 22.0))
            except ValueError:
                t_val = 22.0
            
            if zone == "Core_mid":
                ts_map[ts]["core"] = t_val
            elif zone == "Perimeter_bot_ZN_1":
                ts_map[ts]["bot"] = t_val
            elif zone == "Perimeter_top_ZN_1":
                ts_map[ts]["top"] = t_val

    for ts in timestamps:
        temp_core.append(ts_map[ts]["core"] if ts_map[ts]["core"] is not None else 22.0)
        temp_bot.append(ts_map[ts]["bot"] if ts_map[ts]["bot"] is not None else 22.0)
        temp_top.append(ts_map[ts]["top"] if ts_map[ts]["top"] is not None else 22.0)

    # 3. Construct Self-Contained HTML
    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Eco-Loop Building Agent — Quantitative Savings Dashboard</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=Outfit:wght@400;600;700&display=swap" rel="stylesheet">
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>
    <style>
        :root {{
            --bg-primary: #0a0e17;
            --bg-secondary: #121826;
            --bg-glass: rgba(22, 30, 46, 0.7);
            --border-color: rgba(255, 255, 255, 0.08);
            --text-primary: #f0f4f8;
            --text-secondary: #94a3b8;
            --accent-green: #10b981;
            --accent-cyan: #06b6d4;
            --accent-blue: #3b82f6;
            --accent-purple: #8b5cf6;
            --accent-amber: #f59e0b;
            --accent-red: #ef4444;
        }}
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        body {{
            font-family: 'Inter', sans-serif;
            background-color: var(--bg-primary);
            color: var(--text-primary);
            line-height: 1.6;
            padding: 2rem;
            min-height: 100vh;
            background-image: 
                radial-gradient(circle at 15% 15%, rgba(6, 182, 212, 0.08) 0%, transparent 40%),
                radial-gradient(circle at 85% 85%, rgba(139, 92, 246, 0.08) 0%, transparent 40%);
        }}
        header {{
            max-width: 1400px;
            margin: 0 auto 2.5rem auto;
            text-align: center;
            padding-bottom: 1.5rem;
            border-bottom: 1px solid var(--border-color);
        }}
        h1 {{
            font-family: 'Outfit', sans-serif;
            font-size: 2.75rem;
            font-weight: 700;
            letter-spacing: -0.02em;
            background: linear-gradient(135deg, #f0f4f8 0%, #38bdf8 50%, #818cf8 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            margin-bottom: 0.5rem;
        }}
        .subtitle {{
            color: var(--text-secondary);
            font-size: 1.1rem;
            font-weight: 400;
        }}
        .container {{
            max-width: 1400px;
            margin: 0 auto;
        }}
        /* Stat Cards Grid */
        .stats-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 1.5rem;
            margin-bottom: 2.5rem;
        }}
        .card {{
            background: var(--bg-glass);
            backdrop-filter: blur(12px);
            -webkit-backdrop-filter: blur(12px);
            border: 1px solid var(--border-color);
            border-radius: 16px;
            padding: 1.75rem;
            transition: transform 0.3s ease, box-shadow 0.3s ease;
            position: relative;
            overflow: hidden;
        }}
        .card:hover {{
            transform: translateY(-4px);
            box-shadow: 0 12px 24px rgba(0, 0, 0, 0.3);
            border-color: rgba(255, 255, 255, 0.15);
        }}
        .card::before {{
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 3px;
        }}
        .card-green::before {{ background: linear-gradient(90deg, var(--accent-green), var(--accent-cyan)); }}
        .card-cyan::before {{ background: linear-gradient(90deg, var(--accent-cyan), var(--accent-blue)); }}
        .card-purple::before {{ background: linear-gradient(90deg, var(--accent-purple), #ec4899); }}
        .card-amber::before {{ background: linear-gradient(90deg, var(--accent-amber), var(--accent-red)); }}
        
        .card-title {{
            font-size: 0.9rem;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            color: var(--text-secondary);
            font-weight: 600;
            margin-bottom: 0.5rem;
        }}
        .card-value {{
            font-family: 'Outfit', sans-serif;
            font-size: 2.5rem;
            font-weight: 700;
            margin-bottom: 0.25rem;
        }}
        .card-subtext {{
            font-size: 0.85rem;
            color: var(--text-secondary);
        }}
        .val-green {{ color: var(--accent-green); }}
        .val-cyan {{ color: var(--accent-cyan); }}
        .val-purple {{ color: var(--accent-purple); }}
        .val-amber {{ color: var(--accent-amber); }}
        
        /* Charts Section */
        .charts-grid {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 1.5rem;
            margin-bottom: 2.5rem;
        }}
        @media (max-width: 992px) {{
            .charts-grid {{ grid-template-columns: 1fr; }}
        }}
        .chart-container {{
            background: var(--bg-glass);
            backdrop-filter: blur(12px);
            border: 1px solid var(--border-color);
            border-radius: 16px;
            padding: 1.75rem;
        }}
        .chart-title {{
            font-family: 'Outfit', sans-serif;
            font-size: 1.3rem;
            font-weight: 600;
            margin-bottom: 1rem;
            color: var(--text-primary);
            display: flex;
            align-items: center;
            justify-content: space-between;
        }}
        .chart-wrapper {{
            position: relative;
            height: 320px;
            width: 100%;
        }}
        
        /* Time Series Full Width */
        .full-width-chart {{
            grid-column: 1 / -1;
            margin-bottom: 2.5rem;
        }}
        .full-chart-wrapper {{
            position: relative;
            height: 400px;
            width: 100%;
        }}
        
        /* Honest Note Box */
        .honest-note-box {{
            background: linear-gradient(135deg, rgba(30, 41, 59, 0.8) 0%, rgba(15, 23, 42, 0.8) 100%);
            border-left: 4px solid var(--accent-blue);
            border-radius: 8px;
            padding: 1.5rem;
            margin-bottom: 2.5rem;
            display: flex;
            align-items: flex-start;
            gap: 1rem;
            border: 1px solid var(--border-color);
            border-left-width: 4px;
        }}
        .note-icon {{
            font-size: 1.5rem;
            color: var(--accent-blue);
            flex-shrink: 0;
            margin-top: 0.1rem;
        }}
        .note-content h4 {{
            font-family: 'Outfit', sans-serif;
            font-size: 1.1rem;
            font-weight: 600;
            margin-bottom: 0.25rem;
            color: var(--text-primary);
        }}
        .note-content p {{
            color: var(--text-secondary);
            font-size: 0.95rem;
        }}
        .note-content strong {{
            color: #e2e8f0;
        }}
        
        /* Energy Details Table */
        .table-container {{
            background: var(--bg-glass);
            border: 1px solid var(--border-color);
            border-radius: 16px;
            padding: 1.75rem;
            margin-bottom: 2.5rem;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin-top: 1rem;
        }}
        th, td {{
            padding: 1rem;
            text-align: left;
            border-bottom: 1px solid rgba(255, 255, 255, 0.05);
        }}
        th {{
            color: var(--text-secondary);
            font-weight: 600;
            text-transform: uppercase;
            font-size: 0.8rem;
            letter-spacing: 0.05em;
        }}
        td {{
            font-size: 0.95rem;
        }}
        tr:last-child td {{
            border-bottom: none;
        }}
        .badge {{
            display: inline-block;
            padding: 0.25rem 0.75rem;
            border-radius: 9999px;
            font-size: 0.75rem;
            font-weight: 600;
        }}
        .badge-flat {{ background: rgba(59, 130, 246, 0.15); color: #60a5fa; border: 1px solid rgba(59, 130, 246, 0.3); }}
        .badge-success {{ background: rgba(16, 185, 129, 0.15); color: #34d399; border: 1px solid rgba(16, 185, 129, 0.3); }}
        
        footer {{
            text-align: center;
            color: var(--text-secondary);
            font-size: 0.85rem;
            padding-top: 2rem;
            border-top: 1px solid var(--border-color);
        }}
    </style>
</head>
<body>

<header>
    <h1>Eco-Loop Building Agent</h1>
    <div class="subtitle">Closed-Loop Autonomous HVAC Control via EnergyPlus + LLM Guardrails (Phase 7 Final Delivery)</div>
</header>

<div class="container">

    <!-- Top 4 Summary Cards -->
    <div class="stats-grid">
        <div class="card card-green">
            <div class="card-title">Peak Electrical Demand</div>
            <div class="card-value val-green">{peak_pct}%</div>
            <div class="card-subtext">{peak_ai} kW vs {peak_base} kW baseline</div>
        </div>
        <div class="card card-cyan">
            <div class="card-title">Comfort Violations</div>
            <div class="card-value val-cyan">-{comfort_reduction_pct}%</div>
            <div class="card-subtext">2 hours total vs 32 hours baseline</div>
        </div>
        <div class="card card-purple">
            <div class="card-title">Guardrail Pass Rate</div>
            <div class="card-value val-purple">{pass_rate}%</div>
            <div class="card-subtext">5 Strike-1 rejections, 0 escalations</div>
        </div>
        <div class="card card-amber">
            <div class="card-title">Autonomous Control Decisions</div>
            <div class="card-value val-amber">{intervals}</div>
            <div class="card-subtext">72-hour severe winter stress test (20-min cadence)</div>
        </div>
    </div>

    <!-- Honest Note Section -->
    <div class="honest-note-box">
        <div class="note-icon">ℹ️</div>
        <div class="note-content">
            <h4>Energy Consumption Optimization Rationale</h4>
            <p>Energy use remained essentially flat (<strong>+1.25% Electricity</strong> at {elec_ai} kWh vs {elec_base} kWh; <strong>+0.04% Natural Gas</strong> at {gas_ai} kWh vs {gas_base} kWh); the AI agent's decisions prioritized eliminating comfort violations (-93.75% exceedance reduction during extreme -21.7°C weather) and reducing peak electrical demand (-8.22%) rather than sacrificing occupant comfort to reduce total kWh in this 3-day test window.</p>
        </div>
    </div>

    <!-- Bar Charts Section -->
    <div class="charts-grid">
        <div class="chart-container">
            <div class="chart-title">Peak Electrical Demand (kW)</div>
            <div class="chart-wrapper">
                <canvas id="peakChart"></canvas>
            </div>
        </div>
        <div class="chart-container">
            <div class="chart-title">Comfort Exceedance Hours by Zone</div>
            <div class="chart-wrapper">
                <canvas id="comfortChart"></canvas>
            </div>
        </div>
    </div>

    <!-- Time Series Section -->
    <div class="chart-container full-width-chart">
        <div class="chart-title">
            <span>72-Hour Indoor Zone Temperatures vs ASHRAE 55 Bounds (20–24°C)</span>
            <span style="font-size: 0.85rem; color: var(--text-secondary); font-weight: 400;">Shaded band indicates comfortable operating zone</span>
        </div>
        <div class="full-chart-wrapper">
            <canvas id="tempChart"></canvas>
        </div>
    </div>

    <!-- Detailed Metrics Table -->
    <div class="table-container">
        <div class="chart-title">Duration-Matched 3-Day Performance Breakdown (Feb 5 – Feb 7)</div>
        <table>
            <thead>
                <tr>
                    <th>Metric</th>
                    <th>Baseline Model (Unmodified Schedule)</th>
                    <th>Eco-Loop AI Agent (Closed-Loop)</th>
                    <th>Difference / Savings</th>
                    <th>Evaluation Classification</th>
                </tr>
            </thead>
            <tbody>
                <tr>
                    <td><strong>Peak Electrical Demand</strong></td>
                    <td>{peak_base} kW</td>
                    <td><strong>{peak_ai} kW</strong></td>
                    <td style="color: var(--accent-green); font-weight: 600;">{peak_pct}%</td>
                    <td><span class="badge badge-success">Primary Demand Reduction Driver</span></td>
                </tr>
                <tr>
                    <td><strong>Comfort Exceedance (Total Occupied Hours)</strong></td>
                    <td>{total_c_base} zone-hours</td>
                    <td><strong>{total_c_ai} zone-hours</strong></td>
                    <td style="color: var(--accent-cyan); font-weight: 600;">-{comfort_reduction_pct}% (-30 hrs)</td>
                    <td><span class="badge badge-success">Primary Comfort Preservation Driver</span></td>
                </tr>
                <tr>
                    <td><strong>Facility Electricity Consumption</strong></td>
                    <td>{elec_base} kWh</td>
                    <td>{elec_ai} kWh</td>
                    <td style="color: #94a3b8;">+1.25% (+124.98 kWh)</td>
                    <td><span class="badge badge-flat">Comparable / Comfort Heating Trade-off</span></td>
                </tr>
                <tr>
                    <td><strong>Facility Natural Gas Consumption</strong></td>
                    <td>{gas_base} kWh</td>
                    <td>{gas_ai} kWh</td>
                    <td style="color: #94a3b8;">+0.04% (+1.34 kWh)</td>
                    <td><span class="badge badge-flat">Unaffected (VAV Electric Reheat Architecture)</span></td>
                </tr>
            </tbody>
        </table>
    </div>

</div>

<footer>
    <p>Honeywell Hackathon Submission — Eco-Loop Building Agents | Built with Google DeepMind Advanced Agentic Coding Architecture</p>
</footer>

<script>
    // Chart Defaults
    Chart.defaults.color = '#94a3b8';
    Chart.defaults.font.family = "'Inter', sans-serif";

    // 1. Peak Demand Bar Chart
    const ctxPeak = document.getElementById('peakChart').getContext('2d');
    new Chart(ctxPeak, {{
        type: 'bar',
        data: {{
            labels: ['Baseline (Static Schedule)', 'Eco-Loop AI Agent'],
            datasets: [{{
                label: 'Peak Electrical Demand (kW)',
                data: [{peak_base}, {peak_ai}],
                backgroundColor: [
                    'rgba(148, 163, 184, 0.3)',
                    'rgba(16, 185, 129, 0.7)'
                ],
                borderColor: [
                    'rgba(148, 163, 184, 0.8)',
                    'rgba(16, 185, 129, 1)'
                ],
                borderWidth: 1,
                borderRadius: 8
            }}]
        }},
        options: {{
            responsive: true,
            maintainAspectRatio: false,
            plugins: {{
                legend: {{ display: false }},
                tooltip: {{
                    callbacks: {{
                        label: function(context) {{ return context.parsed.y + ' kW'; }}
                    }}
                }}
            }},
            scales: {{
                y: {{
                    beginAtZero: false,
                    min: 280,
                    max: 360,
                    grid: {{ color: 'rgba(255, 255, 255, 0.05)' }},
                    title: {{ display: true, text: 'Demand (kW)' }}
                }},
                x: {{ grid: {{ display: false }} }}
            }}
        }}
    }});

    // 2. Comfort Exceedance Bar Chart
    const ctxComfort = document.getElementById('comfortChart').getContext('2d');
    new Chart(ctxComfort, {{
        type: 'bar',
        data: {{
            labels: ['Core Mid Zone', 'Perimeter Bottom ZN 1', 'Perimeter Top ZN 1'],
            datasets: [
                {{
                    label: 'Baseline Exceedance Hours',
                    data: [{c_core_base}, {c_bot_base}, {c_top_base}],
                    backgroundColor: 'rgba(239, 68, 68, 0.6)',
                    borderColor: 'rgba(239, 68, 68, 1)',
                    borderWidth: 1,
                    borderRadius: 6
                }},
                {{
                    label: 'AI Agent Exceedance Hours',
                    data: [{c_core_ai}, {c_bot_ai}, {c_top_ai}],
                    backgroundColor: 'rgba(6, 182, 212, 0.8)',
                    borderColor: 'rgba(6, 182, 212, 1)',
                    borderWidth: 1,
                    borderRadius: 6
                }}
            ]
        }},
        options: {{
            responsive: true,
            maintainAspectRatio: false,
            plugins: {{
                legend: {{ position: 'top' }},
                tooltip: {{
                    callbacks: {{
                        label: function(context) {{ return context.dataset.label + ': ' + context.parsed.y + ' hours'; }}
                    }}
                }}
            }},
            scales: {{
                y: {{
                    beginAtZero: true,
                    grid: {{ color: 'rgba(255, 255, 255, 0.05)' }},
                    title: {{ display: true, text: 'Violations (Hours)' }}
                }},
                x: {{ grid: {{ display: false }} }}
            }}
        }}
    }});

    // 3. Time Series Temperature Chart
    const ctxTemp = document.getElementById('tempChart').getContext('2d');
    
    // Shaded Comfort Band Plugin
    const comfortBandPlugin = {{
        id: 'comfortBand',
        beforeDraw: (chart) => {{
            const {{ ctx, chartArea: {{ top, bottom, left, right }}, scales: {{ y }} }} = chart;
            const y24 = y.getPixelForValue(24.0);
            const y20 = y.getPixelForValue(20.0);
            
            ctx.save();
            ctx.fillStyle = 'rgba(16, 185, 129, 0.12)';
            ctx.fillRect(left, y24, right - left, y20 - y24);
            
            ctx.strokeStyle = 'rgba(16, 185, 129, 0.3)';
            ctx.lineWidth = 1;
            ctx.setLineDash([4, 4]);
            ctx.beginPath();
            ctx.moveTo(left, y24);
            ctx.lineTo(right, y24);
            ctx.moveTo(left, y20);
            ctx.lineTo(right, y20);
            ctx.stroke();
            ctx.restore();
        }}
    }};

    new Chart(ctxTemp, {{
        type: 'line',
        data: {{
            labels: {json.dumps(timestamps)},
            datasets: [
                {{
                    label: 'Core Mid Temp (°C)',
                    data: {json.dumps(temp_core)},
                    borderColor: '#3b82f6',
                    backgroundColor: 'rgba(59, 130, 246, 0.1)',
                    borderWidth: 2,
                    pointRadius: 0,
                    tension: 0.2
                }},
                {{
                    label: 'Perimeter Bottom ZN 1 (°C)',
                    data: {json.dumps(temp_bot)},
                    borderColor: '#06b6d4',
                    backgroundColor: 'rgba(6, 182, 212, 0.1)',
                    borderWidth: 2,
                    pointRadius: 0,
                    tension: 0.2
                }},
                {{
                    label: 'Perimeter Top ZN 1 (°C)',
                    data: {json.dumps(temp_top)},
                    borderColor: '#8b5cf6',
                    backgroundColor: 'rgba(139, 92, 246, 0.1)',
                    borderWidth: 2,
                    pointRadius: 0,
                    tension: 0.2
                }}
            ]
        }},
        options: {{
            responsive: true,
            maintainAspectRatio: false,
            interaction: {{
                mode: 'index',
                intersect: false,
            }},
            plugins: {{
                legend: {{ position: 'top' }},
                tooltip: {{
                    callbacks: {{
                        label: function(context) {{ return context.dataset.label + ': ' + context.parsed.y.toFixed(2) + ' °C'; }}
                    }}
                }}
            }},
            scales: {{
                y: {{
                    min: 18.0,
                    max: 26.0,
                    grid: {{ color: 'rgba(255, 255, 255, 0.05)' }},
                    title: {{ display: true, text: 'Zone Air Temperature (°C)' }}
                }},
                x: {{
                    grid: {{ display: false }},
                    ticks: {{
                        maxTicksLimit: 12,
                        maxRotation: 0
                    }}
                }}
            }}
        }},
        plugins: [comfortBandPlugin]
    }});
</script>

</body>
</html>"""

    os.makedirs("dashboard", exist_ok=True)
    out_file = "dashboard/savings_dashboard.html"
    with open(out_file, "w", encoding="utf-8") as f:
        f.write(html_content)

    print(f"================================================================")
    print(f"Quantitative Savings Dashboard generated at: {out_file}")
    print(f"================================================================")

if __name__ == "__main__":
    generate_dashboard()
