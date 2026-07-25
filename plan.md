PHASE 1 — ENVIRONMENT SETUP & VERIFICATION
Project: Eco-Loop Building Agents (Honeywell hackathon closed-loop EnergyPlus + LLM control)

CONTEXT
Host OS: Ubuntu 26.04 LTS, Lenovo laptop, NVIDIA RTX 3060 Mobile (hybrid Optimus/PRIME setup).
GPU is available for local LLM inference — use it, don't default to CPU-only.
Goal of this phase: get every piece of the toolchain installed, isolated, and independently
verified working BEFORE any control-loop code is written. Do not skip verification steps —
a failure here is the single biggest risk to the whole project.

DELIVERABLE OF THIS PHASE
A working dev environment where:
1. EnergyPlus is installed and a sample simulation runs successfully from the CLI.
2. A Python virtual environment exists with the EnergyPlus Python API (pyenergyplus) importable
   and able to run/control a simulation programmatically (not just via CLI).
3. Ollama is installed, using the NVIDIA GPU, with a function-calling-capable model pulled
   and verified to return structured tool-call output.
4. A short markdown file (`SETUP_LOG.md`) documenting exact versions, install paths, and the
   verification command/output for each of the above.

STEP-BY-STEP INSTRUCTIONS

1. System prep
   - Update apt, install build-essential, cmake, git, curl, python3.12-venv (or whatever the
     default Ubuntu 26.04 python3 version is), python3-pip.
   - Confirm NVIDIA driver is active: `nvidia-smi` must show the RTX 3060 Mobile. If it doesn't,
     STOP and report the error rather than proceeding on CPU — this affects LLM latency badly.

2. Project structure
   - Create project root: `~/eco-loop-agents/`
   - Inside it, create a Python virtual environment: `python3 -m venv .venv`
   - Activate it and confirm `which python` points inside `.venv`.
   - All subsequent pip installs happen inside this venv — never system-wide.

3. Install EnergyPlus
   - Download the latest stable EnergyPlus Linux release (.sh installer) for Ubuntu from the
     official EnergyPlus GitHub releases page (search for the current version — do not assume
     a version number, check what's actually current).
   - Run the installer to a known path, e.g. `/usr/local/EnergyPlus-<version>/`.
   - Verify CLI works: run one of the example files shipped with the install
     (e.g. `ExampleFiles/RefBldgMediumOfficeNew2004_Chicago.idf` or similar reference-building
     example — check what example files actually ship with this version) against its paired
     .epw weather file, using the `energyplus` CLI binary. Confirm it completes without errors
     and produces `eplusout.sql` / `eplusout.eso`.
   - Record the exact install path and example file used in SETUP_LOG.md — Phase 2 depends on
     knowing exactly which reference building we're using.

4. Verify the EnergyPlus Python API
   - Inside the venv, locate the `pyenergyplus` module that ships inside the EnergyPlus install
     directory (it is NOT installed via pip — it's bundled with the EnergyPlus install, usually
     under the install root). Add it to the venv's path (via a .pth file or PYTHONPATH export
     documented in SETUP_LOG.md — pick one approach and be consistent).
   - Write a minimal test script `test_api.py` that:
     a. Imports `pyenergyplus.api.EnergyPlusAPI`
     b. Registers a callback on `callback_begin_system_timestep_before_predictor` (or the closest
        equivalent for this EnergyPlus version) that just prints the current sim time once per
        call.
     c. Runs the same example .idf/.epw pair from step 3 through this API-driven path instead
        of the plain CLI.
     d. Confirms the callback actually fires multiple times during the run (print statements
        visible in output) and the run completes successfully.
   - This proves programmatic runtime control is possible — this is the single most important
     checkpoint in this phase. If this doesn't work, report the exact error and do not proceed
     to Phase 2 workarounds without flagging it.

5. Install Ollama and a function-calling model
   - Install Ollama via the official install script.
   - Confirm Ollama is using the GPU (check `ollama ps` / logs show GPU layers offloaded, not
     100% CPU).
   - Pull a model with solid function/tool-calling support suitable for an 8-12GB VRAM budget —
     e.g. `qwen2.5:7b-instruct` or `llama3.1:8b-instruct` (check current Ollama library for the
     best current option in this size class — don't assume, check what's available now).
   - Write a minimal test script `test_llm_tools.py` that sends one prompt with a defined tool
     schema (e.g. a fake `set_temperature(zone: str, value: float)` tool) via Ollama's API and
     confirms the model returns a valid structured tool call (not free text) that can be parsed
     as JSON.

6. Write SETUP_LOG.md
   - EnergyPlus version + install path + example file used for verification
   - Python venv location and Python version
   - pyenergyplus import method used (path/env var)
   - Ollama version, model pulled, confirmation it's using GPU
   - Exact commands used to verify steps 3–5, with a one-line pass/fail note for each

STOP CONDITIONS — report back rather than improvising past these:
- nvidia-smi doesn't show the GPU
- EnergyPlus CLI example run fails
- pyenergyplus callback never fires
- Ollama tool-call output isn't valid parseable JSON

Do not write any control-loop, actuator, or agent logic in this phase — that's Phase 2 onward.
This phase is purely: install, isolate, verify, document.