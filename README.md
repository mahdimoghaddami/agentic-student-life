# Multi-Agent StudentLife Stress Coach (CSI 4900/5900 Project 1)

**Authors:** Mahdi Moghaddami (`mmoghaddami@oakland.edu`) and Brett Piggot (`bpiggot@oakland.edu`)  
**Course:** CSI 4900/5900 — Agentic AI (Fall 2026), Oakland University

A multi-agent, LLM-powered stress-management coach evaluated on longitudinal smartphone sensing, Ecological Momentary Assessment (EMA), survey, and academic schedule data from the **Dartmouth StudentLife dataset** (49 participants over a 10-week spring term). Given a participant at a specific `decision_time`, the system inspects only historical observations up to that timestamp (`t <= decision_time`), consults the student's simulated profile and episodic/preference memory, and decides whether to:
- `suggest`: send a brief, supportive, personalized coaching suggestion (study break, sleep hygiene nudge, gentle movement, social reconnection, deadline chunking, or curated Dartmouth campus resource referral),
- `ask`: ask a low-burden clarifying question when key sensing/self-report modalities are missing or masked, or
- `none`: send no message (`final_message = null`) when the student is doing well or has recently received coaching.

---

## 1. Repository Structure

```text
agentic-student-life/
├─ pyproject.toml                # Dependencies and `asl` CLI entry point
├─ .env.example                  # Environment variable template (GEMINI_API_KEY)
├─ README.md                     # Documentation, schema reference, and run instructions
├─ configs/
│  ├─ full.toml                  # Reference multi-agent configuration (plan=2, refl=2)
│  ├─ ablations.toml             # All 9 ablation configurations
│  └─ judge.toml                 # Fixed independent LLM Judge configuration
├─ cases/
│  ├─ profiles.json              # SIMULATED student profiles grounded in pre-term surveys
│  ├─ cases.jsonl                # 20 deterministic evaluation cases across 5 categories
│  ├─ feedback_scripts.json      # SIMULATED multi-step preference-update feedback scripts
│  └─ selection.md               # Participant coverage ranking & case selection rationale
├─ resources/
│  └─ campus_resources.json      # Curated Dartmouth & 24/7 crisis support resources
├─ skills/                       # 8 modular Markdown coaching skills with TOML headers
│  ├─ micro_study_break.md
│  ├─ sleep_hygiene_nudge.md
│  ├─ gentle_movement.md
│  ├─ social_reconnection.md
│  ├─ deadline_chunking.md
│  ├─ campus_resource_referral.md
│  ├─ clarifying_question.md
│  └─ positive_reinforcement.md
├─ prompts/                      # System prompts for each agent role and the LLM Judge
│  ├─ planner.md
│  ├─ analyst.md
│  ├─ writer.md
│  ├─ critic.md
│  ├─ memory.md
│  ├─ single_agent.md
│  └─ judge.md
├─ src/agentic_student_life/
│  ├─ cli.py                     # CLI (`asl preprocess|cases|run|ablate|judge|human-sheet|analyze|reset-memory`)
│  ├─ config.py                  # TOML config loaders and dataclasses
│  ├─ llm.py                     # aisuite wrapper, Gemini 3 thought_signature patch, retries, JSON repair, tracing
│  ├─ orchestrator.py            # Multi-agent & single-agent pipeline orchestrator
│  ├─ data/                      # Raw StudentLife loaders, daily feature engineering, leak-free View store
│  ├─ tools/                     # Time-bounded sensing, academic, and campus resource tools
│  ├─ memory/                    # Per-run persistent episodic & learned-preference memory store
│  ├─ skills/                    # Skill index and on-demand Markdown skill loader
│  ├─ agents/                    # Planner, Context Analyst, Message Writer, Critic, Memory Manager, Single-Agent
│  ├─ cases/                     # Coverage ranking, simulated profile generator, and 20-case builder
│  └─ eval/                      # LLM Judge, blind human sheet exporter, MAD analyzer, plots, LaTeX tables
├─ tests/
│  └─ test_leakage.py            # Unit tests verifying strict temporal bounds (no future data leakage)
├─ runs/                         # Saved JSONL outputs, call traces, judge scores, human ratings, logs
└─ report/                       # ICML 2026 LaTeX paper (`example_paper.tex`, `example_paper.pdf`, `figures/`, `tables/`)
```

---

## 2. Dependencies & Setup

1. **Python & Package Manager:** Requires Python `>=3.15` and [`uv`](https://docs.astral.sh/uv/).
   - Core dependencies (`pyproject.toml`): `aisuite[gemini]`, `pandas`, `pyarrow`, `numpy`, `pydantic`, `matplotlib`, `scipy`, `python-dotenv`, `tqdm`.
2. **Install environment:**
   ```bash
   uv sync
   ```
3. **Configure API Key:** Copy `.env.example` to `.env` and set your Gemini API key:
   ```bash
   cp .env.example .env
   # Edit .env and set GEMINI_API_KEY=your_api_key_here
   ```
4. **Dataset Location:** Place the raw Kaggle StudentLife dataset under `data/` (`data/sensing/`, `data/EMA/`, `data/education/`, `data/survey/`, `data/call_log/`, `data/sms/`).

---

## 3. How to Run

All commands can be invoked via `uv run asl <subcommand>` (or `.venv/bin/asl <subcommand>`):

### Step 1: Preprocess Raw StudentLife Data into Daily & EMA Feature Parquets
```bash
uv run asl preprocess
```
Builds `cache/features/daily_<uid>.parquet`, `cache/features/ema_<uid>.parquet`, `cache/features/surveys.json`, and `cache/features/academic.json` for all 49 participants (~6 seconds).

### Step 2: Build / Verify Deterministic Evaluation Cases & Simulated Profiles
```bash
uv run asl cases
```
Generates `cases/profiles.json`, `cases/cases.jsonl` (20 cases), `cases/feedback_scripts.json`, and `cases/selection.md`.

### Step 3: Run the Main Evaluation (`configs/full.toml`) and LLM Judge
```bash
uv run asl run --config configs/full.toml --judge
```
- Saves final outputs to `runs/full/outputs.jsonl`
- Saves per-call LLM/tool traces to `runs/full/calls.jsonl`
- Saves execution logs to `runs/full/run.log` and any failed cases to `runs/full/failed_cases.json`
- Saves independent LLM Judge evaluations to `runs/full/judge_scores.jsonl`

### Step 4: Run the Full Ablation Suite
```bash
uv run asl ablate --judge
```
Executes all configurations in `configs/ablations.toml` (`full`, `single`, `no_refl`, `refl1`, `refl3`, `no_plan`, `plan1`, `plan3`, `modelB`) and scores every non-null message with the LLM Judge. Runs are resumable by default; pass `--no-resume` or `--reset-memory` for a clean re-run.

### Step 5: Export the Blind Human Evaluation Sheet & Run Analysis
```bash
uv run asl human-sheet --run-id full
uv run asl analyze
```
- `human-sheet` exports `runs/full/human_eval/blind_rating_sheet.csv` and `blind_rating_sheet.html` (with LLM Judge scores hidden) plus `runs/full/human_eval/human_ratings.json`.
- `analyze` computes all metrics (`runs/summary_metrics.json`), generates publication PDF/PNG plots in `report/figures/`, and generates booktabs LaTeX tables in `report/tables/`.

### Step 6: Memory Reset Instructions
Each configuration run stores its episodic and learned-preference memory in an isolated directory `runs/<run_id>/memory/<uid>.json` so ablations never contaminate one another. To reset memory before a run:
```bash
# Option A: Reset all stored memory across runs
uv run asl reset-memory

# Option B: Reset memory for a single run ID
uv run asl reset-memory --run-id full

# Option C: Pass --reset-memory directly when running cases
uv run asl run --config configs/full.toml --reset-memory --no-resume
```

### Step 7: Run Temporal Leakage Unit Tests
```bash
.venv/bin/python tests/test_leakage.py
```

---

## 4. Output JSONL Schema (`runs/<run_id>/outputs.jsonl`)

Each line in `outputs.jsonl` is a single JSON object representing one test case (`participant_id` at `decision_time`):

| Field | Type | Description |
|---|---|---|
| `case_id` | `str` | Unique case identifier (`case_001` .. `case_020`) |
| `participant_id` | `str` | StudentLife participant ID (e.g., `"u59"`, `"u16"`) |
| `decision_time` | `str` | ISO-8601 timestamp in `America/New_York` (`"2013-04-29T20:00:00-04:00"`) |
| `category` | `str` | Case category (`typical_high_stress`, `typical_doing_fine`, `missing_data`, `preference_update`, `safety_or_restraint`) |
| `episode_id` | `str` | Episode identifier grouping consecutive steps in preference-update episodes |
| `step` | `int` | Interaction step within the episode (`1`, `2`, or `3`) |
| `config_id` | `str` | Configuration ID (`full`, `single`, `no_refl`, `refl1`, `refl3`, `no_plan`, `plan1`, `plan3`, `modelB`) |
| `model` | `str` | Agent LLM identifier (e.g., `"gemini:gemini-3.5-flash"`) |
| `status` | `str` | Execution status (`"ok"` or `"failed"`) |
| `error` | `str \| null` | Error message if `status == "failed"`, otherwise `null` |
| `decision` | `str` | System coaching decision: `"suggest"`, `"ask"`, or `"none"` |
| `expected_decision` | `list[str]` | Acceptable ground-truth decisions for evaluation |
| `skill_used` | `str \| null` | Loaded coaching skill name (or `null` when `decision == "none"`) |
| `plan` | `list[str]` | Information-gathering steps formulated by the Planner |
| `evidence` | `list[dict]` | List of `{source, detail, simulated}` items from sensing/EMA tools (`simulated: false`) and profile/memory (`simulated: true`) |
| `final_message` | `str \| null` | Final student-facing coaching message or clarifying question (`null` when `decision == "none"`) |
| `reflection` | `dict` | `{"rounds_used": int, "critiques": list[str]}` from the Critic review loop |
| `planning` | `dict` | `{"rounds_used": int}` from the Planner–Analyst loop |
| `memory_updates` | `list[str]` | New preference rules extracted by the Memory Manager from simulated student feedback |
| `trace` | `dict` | Efficiency trace: `llm_calls`, `tool_calls`, `prompt_tokens`, `completion_tokens`, `total_tokens`, `latency_s` (excluding judge evaluation), and `per_agent` breakdown |

---

## 5. Case Selection & Labeling of Simulated Information

See [`cases/selection.md`](cases/selection.md) for the full coverage table and per-case rationale:
- **Participant Selection:** All 49 participants were ranked by a coverage score combining EMA stress responses and days with valid sleep, physical activity, and conversation sensing. Six high-coverage participants (`u59`, `u08`, `u19`, `u10`, `u57`, `u16`) plus two additional participants with clean low-stress/natural-gap windows (`u00`, `u02`) were selected.
- **Simulated Profiles (`cases/profiles.json`):** Because StudentLife does not contain personal coaching goals or tone/activity preferences, each selected participant has a deterministic profile explicitly marked `"simulated": true`, grounded in their real pre-term survey scores (`PerceivedStressScale`, `PHQ-9`, `BigFive`, `LonelinessScale`).
- **Simulated Feedback (`cases/feedback_scripts.json` & `cases/cases.jsonl`):** Two 3-step longitudinal episodes (`ep_pref_u16` across `case_013`–`case_015`, and `ep_pref_u59` across `case_016`–`case_018`) include deterministic student feedback marked `"simulated": true` to evaluate cross-episode memory and preference updates.
- **Missing-Data Masks:** `case_009` and `case_010` use real natural sensing gaps (`mask: []`, `mask_simulated: false`), while `case_011` and `case_012` apply synthetic modality masks (`mask_simulated: true`).

---

## 6. Model Settings

| Role | Model ID | Temperature | Notes |
|---|---|---|---|
| **Primary Agents (Model A)** | `gemini:gemini-3-flash-preview` | `0.3` (`0.1` for Critic & Memory Manager) | Used in `full` and structural ablations |
| **Ablation Model B** | `gemini:gemini-3.1-flash-lite` | `0.3` | Used in `modelB` ablation under identical multi-agent configuration |
| **Independent LLM Judge** | `gemini:gemini-3-flash-preview` | `0.0` | Fixed judge instance at temperature `0.0`; scores Context Awareness, Goal Alignment, and Clarity (1–5) |
