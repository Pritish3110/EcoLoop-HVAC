#!/usr/bin/env python3
"""
Phase 4: LLM Prompt Builder
Synthesizes current telemetry, rolling statistical trends, and previous interval feedback
into compact, high-signal system and user prompts for Ollama tool calling.
"""

from typing import List, Dict, Any, Optional
from agent.state_schema import BuildingState

def generate_prompts(
    state: BuildingState,
    last_feedback: Optional[Dict[str, str]] = None
) -> List[Dict[str, str]]:
    """
    Constructs the system and user messages for Ollama chat completion.
    Args:
        state: The current BuildingState instance containing instantaneous sensor values and rolling stats.
        last_feedback: Optional dictionary mapping zone_id to rejection or violation messages from last interval.
    Returns:
        List of message dicts ready for Ollama / OpenAI API chat completion.
    """
    # 1. Build canonical system instructions
    system_prompt = (
        "You control heating/cooling setpoints for 3 zones: Core_mid, Perimeter_bot_ZN_1, and Perimeter_top_ZN_1. "
        "Minimize energy use while keeping zone operative temperature between 20-24°C. "
        "You MUST call set_zone_setpoint for each zone every time you respond, with a rationale.\n\n"
        "OPERATIONAL RULES & BOUNDARIES:\n"
        "- heating_setpoint_c MUST be strictly between 18.0°C and 22.0°C.\n"
        "- cooling_setpoint_c MUST be strictly between 23.0°C and 27.0°C.\n"
        "- heating_setpoint_c MUST be strictly less than cooling_setpoint_c (at least 1.0°C deadband).\n"
        "- Always provide a very brief (under 10 words) technical rationale in each tool call.\n"
        "- Invoke the tool function directly. Do NOT output markdown, conversational filler, or textual explanations outside of tool calls."
    )

    # 2. Build current telemetry summary
    zone_summaries = []
    for z in state.zones:
        z_str = f"- Zone '{z.zone_id}': Current Air Temp = {z.zone_air_temp}°C (Comfort proxy: {z.zone_comfort_proxy}°C)"
        # Check comfort bounds [20.0, 24.0]
        if z.zone_comfort_proxy < 20.0:
            z_str += " [WARNING: BELOW COMFORT BOUND 20.0°C - INCREASE HEATING]"
        elif z.zone_comfort_proxy > 24.0:
            z_str += " [WARNING: ABOVE COMFORT BOUND 24.0°C - DECREASE COOLING]"
        else:
            z_str += " [WITHIN COMFORT BOUNDS]"
        zone_summaries.append(z_str)

    zones_text = "\n".join(zone_summaries)

    # 3. Build rolling trends summary (N=4 control intervals)
    rw = state.rolling_window
    trends_text = (
        f"- Outdoor Air Temp Trend: Min={rw['outdoor_air_temp'].min}°C, Max={rw['outdoor_air_temp'].max}°C, Avg={rw['outdoor_air_temp'].avg}°C\n"
        f"- Facility Elec Rate Trend: Min={rw['facility_electricity_rate'].min} kW, Max={rw['facility_electricity_rate'].max} kW, Avg={rw['facility_electricity_rate'].avg} kW\n"
        f"- Facility Gas Rate Trend: Min={rw['facility_gas_rate'].min} kW, Max={rw['facility_gas_rate'].max} kW, Avg={rw['facility_gas_rate'].avg} kW\n"
    )
    for z_id in ["Core_mid", "Perimeter_bot_ZN_1", "Perimeter_top_ZN_1"]:
        k = f"{z_id}_temp"
        if k in rw:
            trends_text += f"- {z_id} Temp Trend: Min={rw[k].min}°C, Max={rw[k].max}°C, Avg={rw[k].avg}°C\n"

    # 4. Integrate self-correction feedback from previous interval if present
    feedback_text = ""
    if last_feedback and len(last_feedback) > 0:
        fb_lines = ["\nCRITICAL SELF-CORRECTION FEEDBACK FROM LAST INTERVAL:"]
        for zone_id, msg in last_feedback.items():
            fb_lines.append(f"- Zone '{zone_id}': {msg}")
        fb_lines.append("You MUST adjust your proposed setpoints for these zones to avoid repeating rejection or discomfort.")
        feedback_text = "\n".join(fb_lines)

    # 5. Assemble user prompt
    user_prompt = (
        f"Sim Timestamp: {state.sim_timestamp}\n"
        f"Instantaneous Outdoor Air Temp: {state.outdoor_air_temp}°C\n"
        f"Instantaneous Electricity Demand Rate: {state.facility_electricity_rate} kW\n"
        f"Instantaneous Natural Gas Demand Rate: {state.facility_gas_rate} kW\n\n"
        f"CURRENT ZONE TELEMETRY:\n{zones_text}\n\n"
        f"ROLLING STATISTICAL TRENDS (Last 4 Intervals):\n{trends_text.strip()}"
        f"{feedback_text}\n\n"
        "Please evaluate the telemetry and issue tool calls to `set_zone_setpoint` for all 3 target zones now."
    )

    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ]

if __name__ == "__main__":
    from agent.state_schema import ZoneReading, RollingStats
    dummy_state = BuildingState(
        sim_timestamp="2026-07-25 12:00:00",
        outdoor_air_temp=31.5,
        facility_electricity_rate=145.2,
        facility_gas_rate=12.0,
        zones=[
            ZoneReading("Core_mid", 23.5, 23.5),
            ZoneReading("Perimeter_bot_ZN_1", 24.8, 24.8),
            ZoneReading("Perimeter_top_ZN_1", 21.2, 21.2)
        ],
        rolling_window={
            "outdoor_air_temp": RollingStats(30.0, 31.5, 30.8),
            "facility_electricity_rate": RollingStats(130.0, 145.2, 138.0),
            "facility_gas_rate": RollingStats(10.0, 12.0, 11.0),
            "Core_mid_temp": RollingStats(23.0, 23.5, 23.2),
            "Perimeter_bot_ZN_1_temp": RollingStats(24.0, 24.8, 24.4),
            "Perimeter_top_ZN_1_temp": RollingStats(21.0, 21.5, 21.2)
        }
    )
    fb = {"Perimeter_bot_ZN_1": "Last interval setpoint was rejected because cooling setpoint 27.5°C exceeded 27.0°C limit."}
    prompts = generate_prompts(dummy_state, fb)
    import json
    print("Generated Prompts Dump:")
    print(json.dumps(prompts, indent=2))
