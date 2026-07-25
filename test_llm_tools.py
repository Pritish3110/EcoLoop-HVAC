#!/usr/bin/env python3
"""
Phase 1D: LLM Tool-Calling Verification for Ollama & llama3.1:8b
Verifies structured JSON tool-call generation without external dependencies.
"""

import json
import sys
import urllib.request
import urllib.error

OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL_NAME = "llama3.1:8b"

def main():
    print(f"Testing Ollama Tool Calling with Model: {MODEL_NAME}...")

    tools_schema = [
        {
            "type": "function",
            "function": {
                "name": "set_temperature",
                "description": "Set the thermostat temperature setpoint for a specific building zone.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "zone": {
                            "type": "string",
                            "description": "The name of the zone to adjust (e.g. 'Conference_Room_1')."
                        },
                        "value": {
                            "type": "number",
                            "description": "The target temperature in degrees Celsius."
                        }
                    },
                    "required": ["zone", "value"]
                }
            }
        }
    ]

    payload = {
        "model": MODEL_NAME,
        "messages": [
            {
                "role": "user",
                "content": "The conference room is too warm. Please set the zone temperature of 'Conference_Room_1' to 21.5 degrees Celsius."
            }
        ],
        "tools": tools_schema,
        "stream": False
    }

    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(OLLAMA_URL, data=data, headers={"Content-Type": "application/json"})

    try:
        with urllib.request.urlopen(req, timeout=60) as response:
            result = json.loads(response.read().decode("utf-8"))
    except urllib.error.URLError as e:
        print(f"ERROR: Failed to connect to Ollama service at {OLLAMA_URL}: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"ERROR: Exception during inference request: {e}")
        sys.exit(1)

    print("\n--- Response Summary ---")
    message = result.get("message", {})
    tool_calls = message.get("tool_calls", [])

    print(f"Model: {result.get('model')}")
    print(f"Done Reason: {result.get('done_reason')}")
    print(f"Eval Duration: {result.get('eval_duration', 0) / 1e9:.2f} s")

    if not tool_calls:
        print(f"ERROR: No tool calls returned! Assistant content: {message.get('content')}")
        sys.exit(1)

    print(f"\nTool Calls Received ({len(tool_calls)}):")
    for i, tc in enumerate(tool_calls, 1):
        func = tc.get("function", {})
        name = func.get("name")
        args = func.get("arguments")
        print(f"  [{i}] Function: {name}")
        print(f"      Arguments: {json.dumps(args)}")

        if name != "set_temperature":
            print(f"ERROR: Unexpected function name '{name}'")
            sys.exit(1)
        if not isinstance(args, dict) or "zone" not in args or "value" not in args:
            print("ERROR: Tool arguments do not match required schema!")
            sys.exit(1)

    print("\nSUCCESS: Valid structured JSON tool call verified via Ollama API!")
    sys.exit(0)

if __name__ == "__main__":
    main()
