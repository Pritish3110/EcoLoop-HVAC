#!/usr/bin/env python3
"""
Phase 4: Defensive Guardrail Validator
Enforces operational bounds and safety rules on LLM-requested thermostat setpoints.
No LLM decision reaches an EMS actuator without passing through this validation layer.
If validation fails, returns a clear rejection reason to trigger a fallback to last known-good setpoints.
"""

from typing import Tuple, Dict, Any, Optional

VALID_ZONES = {"Core_mid", "Perimeter_bot_ZN_1", "Perimeter_top_ZN_1"}
MIN_HEATING = 18.0
MAX_HEATING = 22.0
MIN_COOLING = 23.0
MAX_COOLING = 27.0
MIN_DEADBAND = 1.0  # Cooling must be greater than heating by at least 1.0°C

class SetpointGuardrail:
    """
    Manages setpoint validation and maintains last known-good fallback values for each target zone.
    """
    def __init__(self):
        # Seeded from original schedule occupied baseline (21.0°C heating, 24.0°C cooling)
        self.last_known_good: Dict[str, Dict[str, float]] = {
            zone: {"heating": 21.0, "cooling": 24.0} for zone in VALID_ZONES
        }

    def validate_setpoint(
        self,
        zone_id: Any,
        heating: Any,
        cooling: Any
    ) -> Tuple[bool, Dict[str, float], str]:
        """
        Validates the proposed heating and cooling setpoints for a zone.
        Returns:
            (is_valid, validated_or_fallback_values, rejection_reason)
        """
        # 1. Validate zone_id
        if not isinstance(zone_id, str) or zone_id not in VALID_ZONES:
            reason = f"Invalid zone_id '{zone_id}'. Must be one of {sorted(list(VALID_ZONES))}."
            return False, {}, reason

        # 2. Type casting and numeric validation
        try:
            htg_val = float(heating)
            clg_val = float(cooling)
        except (ValueError, TypeError) as e:
            reason = f"Setpoint values must be convertible to float. Received heating={heating}, cooling={cooling}. Error: {e}"
            fallback = self.last_known_good[zone_id].copy()
            return False, fallback, reason

        # 3. Check heating boundaries [18.0, 22.0]
        if not (MIN_HEATING <= htg_val <= MAX_HEATING):
            reason = f"Heating setpoint {htg_val}°C is out of bounds [{MIN_HEATING}, {MAX_HEATING}]°C."
            fallback = self.last_known_good[zone_id].copy()
            return False, fallback, reason

        # 4. Check cooling boundaries [23.0, 27.0]
        if not (MIN_COOLING <= clg_val <= MAX_COOLING):
            reason = f"Cooling setpoint {clg_val}°C is out of bounds [{MIN_COOLING}, {MAX_COOLING}]°C."
            fallback = self.last_known_good[zone_id].copy()
            return False, fallback, reason

        # 5. Check deadband ordering (heating < cooling)
        if clg_val - htg_val < MIN_DEADBAND:
            reason = (
                f"Deadband violation: cooling ({clg_val}°C) must be at least {MIN_DEADBAND}°C "
                f"greater than heating ({htg_val}°C)."
            )
            fallback = self.last_known_good[zone_id].copy()
            return False, fallback, reason

        # All checks passed! Round to 2 decimal places and update last known-good memory
        clean_vals = {
            "heating": round(htg_val, 2),
            "cooling": round(clg_val, 2)
        }
        self.last_known_good[zone_id] = clean_vals.copy()
        return True, clean_vals, "PASS"

def validate_setpoint(zone_id: Any, heating: Any, cooling: Any) -> Tuple[bool, Dict[str, float], str]:
    """
    Module-level stateless wrapper for one-off validations.
    """
    guard = SetpointGuardrail()
    return guard.validate_setpoint(zone_id, heating, cooling)

if __name__ == "__main__":
    guard = SetpointGuardrail()
    print("Test 1 (Valid):", guard.validate_setpoint("Core_mid", 21.0, 24.0))
    print("Test 2 (Out of bounds heating):", guard.validate_setpoint("Core_mid", 17.5, 24.0))
    print("Test 3 (Out of bounds cooling):", guard.validate_setpoint("Perimeter_bot_ZN_1", 21.0, 28.0))
    print("Test 4 (Deadband violation):", guard.validate_setpoint("Perimeter_top_ZN_1", 22.0, 22.5))
    print("Test 5 (Invalid zone):", guard.validate_setpoint("Unknown_Zone", 21.0, 24.0))
