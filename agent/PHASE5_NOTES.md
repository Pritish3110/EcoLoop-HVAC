# Phase 5 Architecture & Verification Notes: Guardrail Hardening & Self-Correction Stress Testing

This document summarizes the engineering design, test harnesses, and empirical verification results for **Phase 5** of the Eco-Loop Building Agent project. Phase 5 focuses on stress-testing and hardening the LLM-driven control system to prove enterprise-grade resilience, fail-safe behavior, and autonomous self-correction capabilities.

---

## 1. Guardrail Unit Test Suite Summary (`tests/test_guardrails.py`)

To guarantee that the defensive validation layer (`SetpointGuardrail`) never fails silently or allows out-of-bounds proposals to reach EMS actuators, a standalone unit test suite was built without EnergyPlus dependencies.

### Test Coverage Matrix
*   **Boundary Inclusivity:** Verifies that exact boundary values ($18.0^\circ\text{C}$ / $22.0^\circ\text{C}$ heating, $23.0^\circ\text{C}$ / $27.0^\circ\text{C}$ cooling) are accepted as valid.
*   **Heating Above Max:** Verifies that proposals $> 22.0^\circ\text{C}$ are rejected and revert to fallback.
*   **Cooling Below Min:** Verifies that proposals $< 23.0^\circ\text{C}$ are rejected and revert to fallback.
*   **Deadband Violation:** Verifies that cooling setpoints must exceed heating setpoints by $\ge 1.0^\circ\text{C}$.
*   **Invalid Zone IDs:** Rejects unrecognized target zones.
*   **NaN / None / Non-Numeric Parsing:** Verifies that string noise, `None`, or `math.nan` values are caught defensively without raising Python exceptions or partial assignments.
*   **Negative Temperatures:** Verifies rejection of sub-zero temperature requests.
*   **Atomic Rejection Policy:** Verifies that if one setpoint (e.g., cooling) is invalid while the other (heating) is valid, BOTH revert to the last known-good baseline to prevent unbalanced HVAC states.
*   **Consecutive Rejection Escalation:** Verifies tracking and triggering of the 3-strike escalation rule.

### Execution Results
```bash
PYTHONPATH=. ./.venv/bin/python -m unittest tests/test_guardrails.py
---------
Ran 9 tests in 0.000s
OK (Pass Rate: 100%)
```

---

## 2. Consecutive-Failure Escalation Policy (3-Strike Rule)

In `agent/guardrails.py`, we enhanced `SetpointGuardrail` to track consecutive rejection counts per zone:
$$\text{Rejections}(z) = \text{Rejections}(z) + 1 \quad \text{(on any guardrail violation)}$$

### Escalation Logic & Safe Defaults
*   **Threshold:** If a zone reaches **3 consecutive rejections** ($N \ge 3$), an architectural escalation is triggered.
*   **Safe Default Action:** Instead of indefinitely falling back to the previous "last known-good" value (which might have become outdated or suboptimal as outdoor weather drifted), the zone's memory is forcibly reset to a hardcoded, mid-range **Safe Default**:
    *   **Heating Safe Default:** $20.0^\circ\text{C}$
    *   **Cooling Safe Default:** $24.0^\circ\text{C}$
*   **Recovery:** A single valid tool call from the LLM resets $\text{Rejections}(z) = 0$ and updates the known-good baseline.

---

## 3. Controlled Outage Recovery Verification (`test_outage_recovery.py`)

To prove system resilience against AI service outages (e.g., LLM server crashes, network disconnection, or inference hangs), we simulated a multi-turn service disruption during live control.

### Simulation Protocol & Results
1.  **Turn 1 (Normal Operation):** Connected to Ollama (`http://localhost:11434/api/chat`). All 3 target zones evaluated and validated cleanly.
2.  **Turn 2 & Turn 3 (Simulated Outage):** Forcibly redirected API requests to an unreachable endpoint (`http://localhost:9999/api/chat`) to simulate complete AI service loss.
    *   *Result:* The non-blocking error handler caught `Connection refused`, prevented simulation crash/hang, applied fallback setpoints, and incremented consecutive rejection counters:
        ```text
        [OUTAGE DETECTED] Applying fallback setpoints to all zones without crashing.
        [Core_mid] Fallback Applied -> Htg=21.0, Clg=24.0 (Consecutive Rejections: 1)
        [Core_mid] Fallback Applied -> Htg=21.0, Clg=24.0 (Consecutive Rejections: 2)
        ```
3.  **Turn 4 (Service Restored):** Reconnected to the live Ollama endpoint.
    *   *Result:* The control loop automatically resumed normal closed-loop AI control without requiring a script restart or manual intervention. All consecutive rejection counters reset to `0`:
        ```text
        [Core_mid] Valid=True -> Htg=21.0, Clg=25.0 (Consecutive Rejections: 0)
        SUCCESS: Closed-loop system automatically recovered from 2 continuous outage turns without restarting!
        ```

---

## 4. Self-Correction Loop Proof (`test_self_correction.py`)

A controlled experiment was conducted to prove that the prompt engineering feedback loop (`last_feedback` in `agent/prompt_builder.py`) actively influences and corrects future LLM reasoning.

### Empirical Before/After Comparison
*   **Turn 1 (Initial Call - No Feedback):** The LLM evaluated winter conditions and proposed standard baseline setpoints.
    *   *Result:* `Htg=21.0°C`, `Clg=24.0°C`
    *   *Rationale:* `"Given the current air temperature of 21.0°C and comfort proxy within bounds, no adjustments are needed... The setpoints remain at their current values."`
*   **Forced Feedback Injection:** We injected an artificial guardrail rejection into `last_feedback` for `Core_mid`:
    *   *Feedback Message:* `"Proposed setpoints (Htg:21.0, Clg:24.0) REJECTED: Heating setpoint 21.0°C is too low for current winter draft conditions. You MUST increase heating_setpoint_c to at least 21.5°C in your next tool call to prevent discomfort."`
*   **Turn 2 (Next Interval - With Rejection Feedback):** The LLM received the feedback in its user prompt and re-evaluated the zone.
    *   *Result:* `Htg=21.5°C`, `Clg=24.0°C` (Successfully self-corrected heating setpoint upward by $+0.5^\circ\text{C}$).
    *   *Rationale:* `"Heating setpoint increased to 21.5°C to prevent discomfort due to winter draft conditions, while keeping within the allowed temperature range and maintaining a 1.0°C deadband between heating and cooling setpoints."`

---

## 5. Extended Continuous Stress Test (`agent/control_loop.py`)

We executed an extended multi-hour closed-loop verification run (`MAX_INTERVALS = 36`, representing 12 simulated hours and 108 distinct zone evaluations) to evaluate long-horizon stability, latency drift, and memory footprint.

### Summary Statistics (`logs/phase5_control_log.csv`)
*   **Total Control Intervals Completed:** 36 (12 simulated hours, uninterrupted)
*   **Total Zone Evaluations Logged:** 108 rows
*   **Guardrail Pass Rate:** **100.0%** (108 / 108 passed validation)
*   **Escalation Frequency:** **0** (Zero 3-strike escalations triggered; system maintained stable control)
*   **Simulation Crashes / Hangs:** **0**
*   **Latency Stability Analysis:**
    *   **Average LLM Latency:** $27,852.62\text{ ms}$ ($\sim 27.85\text{ s}$)
    *   **Minimum Latency:** $20,668.03\text{ ms}$ ($\sim 20.67\text{ s}$)
    *   **Maximum Latency:** $41,217.07\text{ ms}$ ($\sim 41.22\text{ s}$)
    *   *Conclusion:* Inference latency remained stable across the 12-hour simulation horizon and comfortably within the 45-second real-time safety timeout budget. No memory leaks or performance degradation were observed.
