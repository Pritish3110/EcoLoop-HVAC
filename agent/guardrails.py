#!/usr/bin/env python3
"""
Phase 5: Hardened Guardrail Validator with Consecutive-Failure Escalation
Enforces operational bounds and safety rules on LLM-requested thermostat setpoints.
No LLM decision reaches an EMS actuator without passing through this validation layer.
If validation fails, returns a clear rejection reason to trigger a fallback to last known-good setpoints.
If a zone experiences 3 consecutive rejections, escalates to a hardcoded safe default (20.0°C/24.0°C).
"""

import math
from typing import Tuple, Dict, Any, Optional

VALID_ZONES = {"Core_mid", "Perimeter_bot_ZN_1", "Perimeter_top_ZN_1"}
MIN_HEATING = 18.0
MAX_HEATING = 22.0
MIN_COOLING = 23.0
MAX_COOLING = 27.0
MIN_DEADBAND = 1.0  # Cooling must be greater than heating by at least 1.0°C
ESCALATION_THRESHOLD = 3
SAFE_DEFAULT = {"heating": 20.0, "cooling": 24.0}

class SetpointGuardrail:
    """
    Manages setpoint validation, maintains last known-good fallback values,
    and tracks consecutive rejections to trigger safe escalation when needed.
    """
    def __init__(self):
        # Seeded from original schedule occupied baseline (21.0°C heating, 24.0°C cooling)
        self.last_known_good: Dict[str, Dict[str, float]] = {
            zone: {"heating": 21.0, "cooling": 24.0} for zone in VALID_ZONES
        }
        self.consecutive_rejections: Dict[str, int] = {
            zone: 0 for zone in VALID_ZONES
        }

    def validate_setpoint(
        self,
        zone_id: Any,
        heating: Any,
        cooling: Any
    ) -> Tuple[bool, Dict[str, float], str, bool]:
        """
        Validates the proposed heating and cooling setpoints for a zone.
        Returns:
            (is_valid, validated_or_fallback_values, rejection_reason, escalated)
        """
        # 1. Validate zone_id
        if not isinstance(zone_id, str) or zone_id not in VALID_ZONES:
            reason = f"Invalid zone_id '{zone_id}'. Must be one of {sorted(list(VALID_ZONES))}."
            return False, {}, reason, False

        # Helper to handle failure recording and escalation check
        def handle_rejection(err_reason: str) -> Tuple[bool, Dict[str, float], str, bool]:
            self.consecutive_rejections[zone_id] += 1
            escalated = False
            if self.consecutive_rejections[zone_id] >= ESCALATION_THRESHOLD:
                # Escalate: replace last_known_good with hardcoded mid-range safe default
                self.last_known_good[zone_id] = SAFE_DEFAULT.copy()
                escalated = True
                err_reason += f" [ESCALATED: Reached {self.consecutive_rejections[zone_id]} consecutive rejections. Resetting to safe default 20.0°C/24.0°C.]"
            fallback = self.last_known_good[zone_id].copy()
            return False, fallback, err_reason, escalated

        # 2. Type casting and numeric validation
        try:
            htg_val = float(heating)
            clg_val = float(cooling)
        except (ValueError, TypeError) as e:
            reason = f"Setpoint values must be convertible to float. Received heating={heating}, cooling={cooling}. Error: {e}"
            return handle_rejection(reason)

        # 3. Check for NaN values explicitly
        if math.isnan(htg_val) or math.isnan(clg_val):
            reason = f"Setpoint values cannot be NaN. Received heating={heating}, cooling={cooling}."
            return handle_rejection(reason)

        # 4. Check heating boundaries [18.0, 22.0]
        if not (MIN_HEATING <= htg_val <= MAX_HEATING):
            reason = f"Heating setpoint {htg_val}°C is out of bounds [{MIN_HEATING}, {MAX_HEATING}]°C."
            return handle_rejection(reason)

        # 5. Check cooling boundaries [23.0, 27.0]
        if not (MIN_COOLING <= clg_val <= MAX_COOLING):
            reason = f"Cooling setpoint {clg_val}°C is out of bounds [{MIN_COOLING}, {MAX_COOLING}]°C."
            return handle_rejection(reason)

        # 6. Check deadband ordering (heating < cooling)
        if clg_val - htg_val < MIN_DEADBAND:
            reason = (
                f"Deadband violation: cooling ({clg_val}°C) must be at least {MIN_DEADBAND}°C "
                f"greater than heating ({htg_val}°C)."
            )
            return handle_rejection(reason)

        # All checks passed! Round to 2 decimal places, update memory, and reset rejection counter
        clean_vals = {
            "heating": round(htg_val, 2),
            "cooling": round(clg_val, 2)
        }
        self.last_known_good[zone_id] = clean_vals.copy()
        self.consecutive_rejections[zone_id] = 0
        return True, clean_vals, "PASS", False

def validate_setpoint(zone_id: Any, heating: Any, cooling: Any) -> Tuple[bool, Dict[str, float], str, bool]:
    """
    Module-level stateless wrapper for one-off validations.
    """
    guard = SetpointGuardrail()
    return guard.validate_setpoint(zone_id, heating, cooling)

if __name__ == "__main__":
    guard = SetpointGuardrail()
    print("Test 1 (Valid):", guard.validate_setpoint("Core_mid", 21.0, 24.0))
    print("Test 2 (Out of bounds heating #1):", guard.validate_setpoint("Core_mid", 17.5, 24.0))
    print("Test 3 (Out of bounds heating #2):", guard.validate_setpoint("Core_mid", 17.0, 24.0))
    print("Test 4 (Out of bounds heating #3 - ESCALATION):", guard.validate_setpoint("Core_mid", 16.5, 24.0))
    print("Test 5 (Valid recovery):", guard.validate_setpoint("Core_mid", 20.0, 24.0))
