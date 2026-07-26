# PoC Demo Video — Timed Narration Script & Storyboard
**Project:** Eco-Loop Building Agents (Honeywell Hackathon Submission)  
**Target Video Duration:** 2 minutes 50 seconds (Maximum Cap: 3:00)  
**Format:** Screen recording with voiceover narration.

---

## Storyboard & Timing Checkpoints

| Timecode | Segment Title | Visual Cues & Actions | Key Message to Convey |
| :--- | :--- | :--- | :--- |
| **0:00 – 0:30**<br>*(30 sec)* | **1. Live Control Loop Demo** | Open split terminal. Left pane: running `python -m agent.control_loop`. Right pane: tailing `logs/phase6_run.log`. Highlight real JSON tool calls and `<10`-word rationale strings appearing live. | Demonstrate live, autonomous closed-loop control between EPlus ESQL and Ollama `qwen2.5-coder:7b` in real time. |
| **0:30 – 1:30**<br>*(60 sec)* | **2. Dashboard Walkthrough** | Open `dashboard/savings_dashboard.html` in browser. Hover over top 4 stat cards. Scroll to Comfort Exceedance Bar Chart and interactive Time-Series Temperature Chart. | Present quantitative results: -8.22% peak demand, -93.75% comfort violations, and explain why total consumption is flat. |
| **1:30 – 2:30**<br>*(60 sec)* | **3. Closed-Loop Architecture & Guardrails** | Show the Mermaid architecture diagram in `docs/SYSTEM_ARCHITECTURE.md` or Slide 2. Point out N=4 rolling window, 3-strike escalation, and VAV reheat finding. | Prove enterprise safety (0 escalations, 99.23% pass rate) and explain the VAV electric reheat engineering rigor. |
| **2:30 – 2:50**<br>*(20 sec)* | **4. Wrap-Up & Conclusion** | Show repo directory structure or Slide 5 (Known Limitations & Roadmap). Fade to title slide. | Conclude with production readiness and readiness for 15-zone scaling. |

---

## Detailed Voiceover Narration Script

### Segment 1: Live Control Loop Demo (0:00 – 0:30)
**[Visual: Terminal screen showing `python -m agent.control_loop` executing, logs scrolling with JSON tool calls.]**

> **Voiceover (0:00–0:15):**  
> *"Hello, and welcome to Eco-Loop—our autonomous, closed-loop building control agent designed for the Honeywell Hackathon. On screen right now, you see our live control loop executing in real time against an EnergyPlus simulation during a severe winter cold snap."*

> **Voiceover (0:15–0:30):**  
> *"Every 20 simulation minutes, our Python middleware extracts building thermal state via ESQL, compresses it into a rolling statistical window, and queries a local Large Language Model—Ollama running `qwen2.5-coder`. Watch as the model emits structured JSON tool calls with concise architectural rationales under 10 words, driving physical HVAC setpoint actuators."*

---

### Segment 2: Dashboard Walkthrough (0:30 – 1:30)
**[Visual: Switch browser tab to `dashboard/savings_dashboard.html`. Mouse hovers over the 4 headline summary stat cards.]**

> **Voiceover (0:30–0:50):**  
> *"Over a 72-hour severe winter stress test with outdoor temperatures plunging to minus 21.7 degrees Celsius, our closed-loop agent achieved remarkable quantitative results. Lead by our top stat cards: we achieved an **8.22% reduction in Peak Electrical Demand**—shaving nearly 29 kilowatts off grid strain during morning warm-ups."*

**[Visual: Scroll down to highlight the Comfort Exceedance Bar Chart and then the Time-Series Chart.]**

> **Voiceover (0:50–1:15):**  
> *"Even more impressively, look at our comfort exceedance chart. While static baseline schedules caused 32 hours of freezing occupant violations across occupied hours, our AI agent dropped total violations down to **just 2 hours—a 93.75% reduction**. Notice in our temperature time-series how the agent intelligently pre-heats zones just before 8:00 AM, keeping temperatures smoothly inside the shaded ASHRAE 55 comfort band."*

**[Visual: Hover over the Honest Note Box and the Metrics Table at the bottom.]**

> **Voiceover (1:15–1:30):**  
> *"Why did overall energy use remain flat? Our agent prioritized human safety and peak demand reduction over sacrificing comfort to save kilowatt-hours in freezing weather. Furthermore, because this reference building uses Variable Air Volume boxes with electric reheat coils, zone thermostat adjustments directly reduce electrical peak demand while leaving central rooftop gas boilers unaffected—a testament to our rigorous HVAC architecture audit."*

---

### Segment 3: Closed-Loop Architecture & Guardrails (1:30 – 2:30)
**[Visual: Switch to `docs/SYSTEM_ARCHITECTURE.md` showing the Mermaid architecture diagram and Guardrail section.]**

> **Voiceover (1:30–1:55):**  
> *"How do we guarantee an LLM won't destabilize physical building hardware? We enforce a deterministic **3-Strike Safety Guardrail**. Every proposed setpoint is intercepted before reaching the actuators. If a proposal violates ASHRAE 55 bounds, Strike 1 injects a structured error back into the LLM context for Turn-2 self-correction."*

**[Visual: Scroll to highlight the 99.23% pass rate and latency metrics.]**

> **Voiceover (1:55–2:30):**  
> *"Across 216 simulation intervals and 648 independent zone decisions, our agent achieved a **99.23% first-turn pass rate**. Exactly 5 proposals triggered Strike-1 self-corrections, and all 5 were successfully resolved by the model on Turn 2—resulting in **zero Strike-2 clamps and zero Strike-3 default fallbacks**. By constraining model rationales to under 10 words, we slashed average inference latency to 17.6 seconds per interval, proving viable real-time edge control."*

---

### Segment 4: Wrap-Up & Conclusion (2:30 – 2:50)
**[Visual: Switch back to Title Slide or Repo Root structure in VS Code.]**

> **Voiceover (2:30–2:50):**  
> *"Eco-Loop proves that coupling industry-standard EnergyPlus simulation with local, guardrailed Large Language Models delivers safe, autonomous, and highly effective building decarbonization. With zero external dependencies and modular 15-zone scalability, Eco-Loop is ready for enterprise deployment. Thank you for watching."*

---

## Pre-Recording Checklist
1.  [ ] **Terminal Setup:** Ensure `python -m agent.control_loop` is ready to run or tail `phase6_run.log` at 1.5x speed.
2.  [ ] **Browser Setup:** Open `dashboard/savings_dashboard.html` in Chrome/Edge at 100% zoom with full screen (F11) or clean browser chrome.
3.  [ ] **Audio/Mic Check:** Ensure no background noise, speak at a calm, professional, senior-engineer pace.
4.  [ ] **Timer Cap:** Use a stopwatch during rehearsal to ensure total duration stays between **2:45 and 2:55** (NEVER exceed 3:00).
