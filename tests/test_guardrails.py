#!/usr/bin/env python3
"""
Phase 5: Pure Unit Test Suite for SetpointGuardrail
Tests unhappy paths, boundary inclusivity, non-numeric parsing, deadband checks,
atomic rejection policy, and consecutive rejection escalation without EnergyPlus dependencies.
"""

import unittest
import math
from agent.guardrails import SetpointGuardrail, VALID_ZONES, SAFE_DEFAULT

class TestSetpointGuardrail(unittest.TestCase):
    def setUp(self):
        self.guard = SetpointGuardrail()

    def test_boundary_inclusivity(self):
        """Assert valid setpoints at exact lower/upper boundaries are accepted."""
        # Lower bound: 18.0 heating, 23.0 cooling
        is_val, vals, reason, esc = self.guard.validate_setpoint("Core_mid", 18.0, 23.0)
        self.assertTrue(is_val, f"Failed lower bound check: {reason}")
        self.assertEqual(vals, {"heating": 18.0, "cooling": 23.0})
        self.assertFalse(esc)

        # Upper bound: 22.0 heating, 27.0 cooling
        is_val, vals, reason, esc = self.guard.validate_setpoint("Core_mid", 22.0, 27.0)
        self.assertTrue(is_val, f"Failed upper bound check: {reason}")
        self.assertEqual(vals, {"heating": 22.0, "cooling": 27.0})
        self.assertFalse(esc)

    def test_heating_above_max(self):
        """Assert heating > 22.0 is rejected and falls back cleanly."""
        is_val, vals, reason, esc = self.guard.validate_setpoint("Core_mid", 22.1, 25.0)
        self.assertFalse(is_val)
        self.assertIn("out of bounds", reason)
        self.assertEqual(vals, {"heating": 21.0, "cooling": 24.0})  # initial baseline

    def test_cooling_below_min(self):
        """Assert cooling < 23.0 is rejected and falls back cleanly."""
        is_val, vals, reason, esc = self.guard.validate_setpoint("Core_mid", 20.0, 22.9)
        self.assertFalse(is_val)
        self.assertIn("out of bounds", reason)
        self.assertEqual(vals, {"heating": 21.0, "cooling": 24.0})

    def test_deadband_violation(self):
        """Assert cooling - heating < 1.0 is rejected."""
        is_val, vals, reason, esc = self.guard.validate_setpoint("Core_mid", 21.5, 22.0)
        self.assertFalse(is_val)
        self.assertEqual(vals, {"heating": 21.0, "cooling": 24.0})

    def test_invalid_zone_id(self):
        """Assert unrecognized zone_id is rejected."""
        is_val, vals, reason, esc = self.guard.validate_setpoint("Invalid_Zone", 20.0, 24.0)
        self.assertFalse(is_val)
        self.assertIn("Invalid zone_id", reason)
        self.assertEqual(vals, {})

    def test_nan_and_none_values(self):
        """Assert NaN or None inputs are safely caught and rejected without raising exceptions."""
        is_val, vals, reason, esc = self.guard.validate_setpoint("Core_mid", None, 25.0)
        self.assertFalse(is_val)
        self.assertIn("convertible to float", reason)
        self.assertEqual(vals, {"heating": 21.0, "cooling": 24.0})

        is_val, vals, reason, esc = self.guard.validate_setpoint("Perimeter_bot_ZN_1", 20.0, "invalid_str")
        self.assertFalse(is_val)
        self.assertIn("convertible to float", reason)
        self.assertEqual(vals, {"heating": 21.0, "cooling": 24.0})

        is_val, vals, reason, esc = self.guard.validate_setpoint("Perimeter_top_ZN_1", math.nan, 25.0)
        self.assertFalse(is_val)
        self.assertIn("cannot be NaN", reason)
        self.assertEqual(vals, {"heating": 21.0, "cooling": 24.0})

    def test_negative_temperatures(self):
        """Assert negative setpoint values are rejected."""
        is_val, vals, reason, esc = self.guard.validate_setpoint("Core_mid", -5.0, 25.0)
        self.assertFalse(is_val)
        self.assertIn("out of bounds", reason)
        self.assertEqual(vals, {"heating": 21.0, "cooling": 24.0})

    def test_atomic_rejection_no_partial_application(self):
        """Assert that if cooling is invalid but heating is valid, BOTH are rejected and reverted to fallback."""
        # First, set a valid state
        self.guard.validate_setpoint("Core_mid", 19.0, 25.0)
        self.assertEqual(self.guard.last_known_good["Core_mid"], {"heating": 19.0, "cooling": 25.0})

        # Now try valid heating (18.5) but invalid cooling (28.0)
        is_val, vals, reason, esc = self.guard.validate_setpoint("Core_mid", 18.5, 28.0)
        self.assertFalse(is_val)
        # Verify heating did NOT change to 18.5! Both reverted to last known good (19.0, 25.0)
        self.assertEqual(vals, {"heating": 19.0, "cooling": 25.0})
        self.assertEqual(self.guard.last_known_good["Core_mid"], {"heating": 19.0, "cooling": 25.0})

    def test_consecutive_rejection_escalation(self):
        """Assert 3 consecutive rejections trigger escalation to SAFE_DEFAULT."""
        # Rejection 1
        is_val, vals, reason, esc = self.guard.validate_setpoint("Perimeter_bot_ZN_1", 15.0, 25.0)
        self.assertFalse(is_val)
        self.assertFalse(esc)
        self.assertEqual(self.guard.consecutive_rejections["Perimeter_bot_ZN_1"], 1)

        # Rejection 2
        is_val, vals, reason, esc = self.guard.validate_setpoint("Perimeter_bot_ZN_1", 15.0, 25.0)
        self.assertFalse(is_val)
        self.assertFalse(esc)
        self.assertEqual(self.guard.consecutive_rejections["Perimeter_bot_ZN_1"], 2)

        # Rejection 3 - ESCALATION!
        is_val, vals, reason, esc = self.guard.validate_setpoint("Perimeter_bot_ZN_1", 15.0, 25.0)
        self.assertFalse(is_val)
        self.assertTrue(esc)
        self.assertIn("ESCALATED", reason)
        self.assertEqual(vals, SAFE_DEFAULT)
        self.assertEqual(self.guard.last_known_good["Perimeter_bot_ZN_1"], SAFE_DEFAULT)

        # A subsequent valid call resets consecutive rejections to 0
        is_val, vals, reason, esc = self.guard.validate_setpoint("Perimeter_bot_ZN_1", 20.5, 24.5)
        self.assertTrue(is_val)
        self.assertFalse(esc)
        self.assertEqual(self.guard.consecutive_rejections["Perimeter_bot_ZN_1"], 0)

if __name__ == "__main__":
    unittest.main()
