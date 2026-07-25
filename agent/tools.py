#!/usr/bin/env python3
"""
Phase 4: LLM Tool Calling Schema
Defines the tool schema for Ollama / OpenAI-compatible tool calling in closed-loop HVAC control.
Bakes temperature boundaries and operational constraints directly into the tool description text.
"""

from typing import List, Dict, Any

def get_tools_schema() -> List[Dict[str, Any]]:
    """
    Returns the tool definition schema for setting zone heating and cooling thermostat setpoints.
    """
    return [
        {
            "type": "function",
            "function": {
                "name": "set_zone_setpoint",
                "description": (
                    "Set the heating and cooling thermostat setpoint temperatures for a specific thermal zone. "
                    "CRITICAL OPERATIONAL BOUNDS AND CONSTRAINTS:\n"
                    "1. heating_setpoint_c MUST be strictly between 18.0°C and 22.0°C (inclusive: 18.0 <= heating <= 22.0).\n"
                    "2. cooling_setpoint_c MUST be strictly between 23.0°C and 27.0°C (inclusive: 23.0 <= cooling <= 27.0).\n"
                    "3. heating_setpoint_c MUST always be strictly less than cooling_setpoint_c (heating < cooling) with at least 1.0°C deadband.\n"
                    "4. You MUST provide a clear, concise technical rationale explaining why this setpoint decision balances energy efficiency and ASHRAE 55 operative comfort (20.0°C to 24.0°C)."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "zone_id": {
                            "type": "string",
                            "enum": ["Core_mid", "Perimeter_bot_ZN_1", "Perimeter_top_ZN_1"],
                            "description": "The unique identifier of the target thermal zone to control."
                        },
                        "heating_setpoint_c": {
                            "type": "number",
                            "description": "Target heating thermostat setpoint in degrees Celsius. MUST be between 18.0 and 22.0."
                        },
                        "cooling_setpoint_c": {
                            "type": "number",
                            "description": "Target cooling thermostat setpoint in degrees Celsius. MUST be between 23.0 and 27.0 and strictly greater than heating_setpoint_c."
                        },
                        "rationale": {
                            "type": "string",
                            "description": "Short, technical explanation of the reasoning behind this setpoint decision based on current telemetry, rolling trends, and comfort bounds."
                        }
                    },
                    "required": ["zone_id", "heating_setpoint_c", "cooling_setpoint_c", "rationale"]
                }
            }
        }
    ]

if __name__ == "__main__":
    import json
    print(json.dumps(get_tools_schema(), indent=2))
