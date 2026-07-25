PHASE 6 — MULTI-DAY UNATTENDED ROBUSTNESS RUN & PROJECT DOCUMENTATION
Project: Eco-Loop Building Agents (Honeywell hackathon closed-loop EnergyPlus + LLM control)

CONTEXT — CARRY THESE FORWARD EXACTLY
- Phase 5 result: 12-hr run, 108/108 guardrail passes, 0 escalations, 0 crashes, latency
  stable 20.67s-41.22s avg 27.85s. Self-correction and outage recovery both proven.
- logs/baseline_kpis.json — golden, immutable: Facility Elec 767,958.33 kWh, Gas 60,361.11 kWh,
  Peak Demand 344.93 kW
- agent/control_loop.py, guardrails.py, prompt_builder.py, state_schema.py, tools.py — all
  verified stable through Phase 5
- Venv: /home/pritish_3110/Personal Files/Syllabus/Projects/honeywell_hackathon/.venv,
  Python 3.14.4
- EnergyPlus v26.1.0 at /home/pritish_3110/.local/EnergyPlus-26-1-0
- Weather: USA_IL_Chicago-OHare.Intl.AP.725300_TMY3.epw

GOAL OF THIS PHASE
Two deliverables, do both:
(A) Run the full closed-loop system unattended for a genuinely extended horizon (multi-day,
    ideally covering a full week including a weather swing) to produce the final robustness
    evidence for the 30%-weighted System Integration score, and the final AI-run KPI numbers
    to compare against the golden baseline.
(B) Write the complete GitHub-facing documentation set — README.md and REQUIREMENTS.md — written
    so a judge or a new developer can understand and reproduce the project from zero context.

STEP-BY-STEP INSTRUCTIONS

1. Configure and launch the extended run
   - Set actuator_ready.idf's RunPeriod to cover at least 7 simulated days, ideally chosen from
     the TMY3 weather file to include both a cold stretch and a milder stretch (check the epw
     for temperature range across the year if unsure which week to pick, document your choice).
   - Launch via `./.venv/bin/python -m agent.control_loop`, backgrounded (nohup or equivalent)
     so it survives terminal disconnection, logging stdout to `logs/phase6_run.log`.
   - Let it run to completion unattended. Do not manually intervene unless it hangs — if it
     hangs, that itself is the most important finding to report.

2. Extract final AI-run KPIs
   - From the completed run's eplusout.sql, extract the same fields as baseline_kpis.json
     (total facility electricity, gas, peak demand) plus total control intervals executed,
     total guardrail rejections, total escalations, and comfort-violation hours (using the
     same operative-temp proxy as Phase 3).
   - Save to `logs/ai_run_kpis.json`.
   - Compute and save `logs/final_comparison.json`: % electricity change, % gas change, % peak
     demand change, comfort violation hours (AI run) vs baseline, all relative to
     baseline_kpis.json. This is your actual scored result — get the arithmetic right and
     double check the sign (negative = savings).

3. Update agent/PHASE6_NOTES.md
   - Run duration (sim days), total control intervals, total guardrail rejections/escalations,
     latency stats across the full run (avg/min/max, and whether it drifted vs Phase 5's 12-hr
     numbers), any hangs or anomalies observed, and the final comparison numbers from step 2.

4. Write README.md (project root) — must include, in this order:
   a. Project title + one-paragraph summary of what it does and why (closed-loop LLM control
      of EnergyPlus building simulation for energy savings with comfort constraints) — written
      for a judge with zero prior context, not just for a developer.
   b. Architecture diagram or clearly described data flow: EnergyPlus → state pipeline → prompt
      builder → LLM (Ollama) → guardrails → actuators → back to EnergyPlus. Reference the actual
      module names (agent/state_schema.py, agent/guardrails.py, etc.) so a reader can map the
      description to the repo.
   c. Project folder structure — a full tree of the actual repo (models/, agent/, logs/, tests/,
      the SETUP_LOG.md and NOTES files) with a one-line description of what each directory/file
      contains. Generate this from the actual current directory structure, don't guess it.
   d. Key results section: baseline vs AI-run KPI comparison table (from final_comparison.json),
      stated plainly (e.g. "X% electricity reduction, Y% gas reduction, comfort maintained
      within Z hours of violation") — this is the first thing a judge will look for.
   e. "First-Time Setup" section — from a fresh clone, exact ordered commands to: create the
      venv, install all Python dependencies, install EnergyPlus (or a note that a working
      EnergyPlus install path must be supplied — since EnergyPlus itself isn't a pip package),
      configure the .pth file for pyenergyplus, install Ollama, pull the required model.
      Reference REQUIREMENTS.md for the exhaustive dependency list rather than duplicating it.
   f. "Running the Project" section, split clearly into:
      - First-time / full pipeline run: baseline generation → state pipeline verification →
        full control loop run → KPI comparison, with the actual exact commands used in this
        project (pull real command strings from SETUP_LOG.md, don't invent new ones)
      - Subsequent / repeat runs: the shorter path once the environment already exists (e.g.
        just activating venv + running control_loop.py, without re-running baseline extraction)
   g. Known limitations section — briefly and honestly note things like: control interval
      granularity, 3-zone scope rather than full-building, single-model LLM choice, latency
      characteristics — a few honest lines score better with judges than overclaiming.
   h. Team/attribution line — your name (Pritish, Miraiminds background optional), hackathon
      name.

5. Write REQUIREMENTS.md (project root) — must include:
   a. OS/hardware assumptions actually used in this project: Ubuntu 26.04 LTS, NVIDIA GPU
      (state the RTX 3060 Mobile as what was tested on, and that a GPU is recommended but not
      strictly required — CPU inference would just be slower, note the latency implication).
   b. EnergyPlus: exact version (v26.1.0-6f2e40d102), where to download it (official GitHub
      releases), and that its install path must be reflected wherever the project's .pth file
      or PYTHONPATH config points — reference the actual mechanism used.
   c. Python version used (3.14.4) and exact venv creation commands.
   d. A complete, pinned `requirements.txt`-equivalent list — actually run
      `./.venv/bin/pip freeze` and include the real output, don't hand-write approximate package
      names/versions.
   e. Ollama: install method, exact model pulled (llama3.1:8b) and the exact `ollama pull`
      command, and confirmation of the GPU offload check command (`ollama ps`).
   f. Any other non-pip system packages required (build-essential, cmake, python3-venv, etc. —
      whatever was actually installed in Phase 1, pull from SETUP_LOG.md rather than guessing).

STOP CONDITIONS — report back rather than improvising past these:
- The extended run hangs or crashes at any point (report exactly where and any error output)
- final_comparison.json shows an INCREASE in both energy and comfort violations (i.e. the AI
  strictly underperforms baseline on both fronts) — this would need investigation before
  packaging it as a result
- pip freeze output is inconsistent with what's actually importable (indicates a broken venv
  state that needs fixing before documenting it as reproducible)

Do not build the visual dashboard in this phase — that's Phase 7, along with the architecture
document (distinct from README.md — Phase 7's system architecture doc covers prompt engineering
strategy and latency management in deliverable-spec detail) and the demo video/slides.