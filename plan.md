PHASE 4 — LLM AGENT DECISION LOOP (CLOSING THE LOOP)
Project: Eco-Loop Building Agents (Honeywell hackathon closed-loop EnergyPlus + LLM control)

CONTEXT — CARRY THESE FORWARD EXACTLY
- EnergyPlus v26.1.0, actuator_ready.idf (3 target zones: Core_mid, Perimeter_bot_ZN_1,
  Perimeter_top_ZN_1), 6 EMS actuators on Schedule:Constant objects, all handles verified valid
- agent/state_schema.py — BuildingState, ZoneReading, RollingStats, RollingWindowTracker (N=4
  control intervals), already verified producing clean data at the established control cadence
  (72 intervals/day per Phase 3's trace)
- logs/baseline_kpis.json — GOLDEN, IMMUTABLE. Facility Elec 767,958.33 kWh, Gas 60,361.11 kWh,
  Peak Demand 344.93 kW. Do not regenerate. This is the number to beat.
- Ollama: llama3.1:8b running locally, GPU-offloaded, ~2.14s per call verified in Phase 1
- Comfort proxy: operative temperature 20–24°C (established in Phase 3, not PMV — check
  BUILDING_NOTES.md for exact rationale if unsure)
- Venv: /home/pritish_3110/Personal Files/Syllabus/Projects/honeywell_hackathon/.venv

GOAL OF THIS PHASE
Replace the Phase 2 hardcoded override rule with a real LLM decision at every control interval:
BuildingState → LLM (via tool-calling) → validated setpoint → EMS actuator. This is the actual
closed loop the hackathon is scoring. Keep it defensive — a single bad LLM call must never crash
the simulation or leave a zone in an unsafe state.

STEP-BY-STEP INSTRUCTIONS

1. Define the tool schema — agent/tools.py
   - One tool: `set_zone_setpoint(zone_id: str, heating_setpoint_c: float, cooling_setpoint_c: float, rationale: str)`
   - `rationale` is REQUIRED in the schema (short string) — this is what makes Agentic Autonomy
     scoring visible later and gives you the reasoning trail for the architecture doc.
   - Hard bounds baked into the schema description (not just enforced later): heating 18–22°C,
     cooling 23–27°C, heating_setpoint_c must always be < cooling_setpoint_c. Tell the LLM these
     bounds explicitly in the tool description text.

2. Build the guardrail/bounds validator — agent/guardrails.py
   - `validate_setpoint(zone_id, heating, cooling) -> (bool, cleaned_values, reason)`
   - Enforce: 18 ≤ heating ≤ 22, 23 ≤ cooling ≤ 27, heating < cooling, zone_id is one of the 3
     valid target zones.
   - If invalid: DO NOT apply. Return the reason. The control loop must fall back to the last
     known-good setpoint for that zone (persist last-good values in memory, seeded from the
     zone's original schedule value at sim start).
   - This is the single most important file for your System Integration score — no LLM output
     reaches an actuator without passing through this first.

3. Build the prompt builder — agent/prompt_builder.py
   - Input: a BuildingState instance (current + rolling window from RollingWindowTracker)
   - Output: a compact system+user prompt, NOT a raw dump of all fields — summarize the rolling
     window as already-computed min/max/avg (it already is, per Phase 3 schema), state the
     current outdoor temp, current per-zone temps, and current energy rate.
   - Explicitly instruct the LLM in the system prompt: "You control heating/cooling setpoints
     for 3 zones. Minimize energy use while keeping zone operative temperature between 20–24°C.
     You MUST call set_zone_setpoint for each zone every time you respond, with a rationale."
   - If the previous interval had a guardrail rejection or comfort violation, include that as
     context ("last interval, Zone X setpoint was rejected because Y" / "Zone X was outside
     comfort range last interval") — this is your self-correction loop.

4. Build the control loop manager — agent/control_loop.py
   - Wraps the EnergyPlusAPI callback pattern from Phases 1–3.
   - At each control interval (same cadence as Phase 3's state pipeline, NOT every timestep):
     a. Build BuildingState (reuse Phase 3 pipeline code, don't duplicate it)
     b. Build prompt via prompt_builder
     c. Call Ollama with the tool schema, with a hard timeout (e.g. 10s — if it exceeds this,
        treat as failure, do not block the simulation indefinitely)
     d. Parse tool calls for all 3 zones. If the LLM didn't call the tool for a zone, or the
        response isn't parseable JSON, treat as failure for that zone.
     e. Run every result through guardrails.validate_setpoint
     f. Apply validated setpoints via set_actuator_value; on any failure/rejection, apply last
        known-good value instead and log why
     g. Log EVERY interval to `logs/phase4_control_log.csv`: sim_time, zone, requested_heating,
        requested_cooling, applied_heating, applied_cooling, guardrail_pass (bool),
        rationale_text, llm_latency_ms

5. Run a short verification run first
   - Run for 1 simulated day only first (fast iteration). Confirm:
     - No crash
     - control_log.csv shows a mix of LLM decisions being applied
     - At least manually inspect 5–10 rationale strings to confirm they're coherent, not garbage
   - Only proceed to a longer run once this looks sane — do not jump straight to a long run.

6. Update BUILDING_NOTES.md / create agent/PHASE4_NOTES.md
   - Control interval cadence used and why
   - Guardrail bounds and fallback behavior
   - Sample of 3–5 rationale strings from the log, as evidence the reasoning loop works
   - Any LLM timeout/failure rate observed in the 1-day test run

STOP CONDITIONS — report back rather than improvising past these:
- Simulation crashes or hangs waiting on an LLM call
- Guardrail validator lets an out-of-bounds setpoint through (this must never happen — treat
  as a critical bug, not a minor issue)
- LLM tool call fails to parse for the majority of intervals (indicates prompt/schema problem,
  not a hardware issue — do not just retry blindly, inspect actual raw LLM output)

Do NOT run the full extended simulation in this phase — that's Phase 6 (robustness). This phase
only proves the loop works correctly for a short run. Phase 5 hardens guardrails/self-correction
further if needed; Phase 6 is the long unattended run.