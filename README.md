# Multi-Agent StudentLife Stress Coach

**Authors:** Mahdi Moghaddami and Brett Piggott
**Course:** CSI 4900/5900 Agentic AI, Oakland University

The coach uses StudentLife observations, a simulated student profile and earlier interactions to suggest a supportive action, ask a clarifying question, or remain silent. No model training is required.

[Report](output/pdf/studentlife_coach_paper/studentlife_coach.pdf) | [Saved evaluation results](runs_corrected/2026-11-04_v3/summary_metrics.json)

## Code structure

- `src/agentic_student_life/`: CLI, orchestration, data processing, agents, tools, memory, skills and evaluation.
- `configs/`: model settings and component controls; `evaluation.toml` defines all nine conditions.
- `cases/`: evaluation cases, simulated profiles, feedback scripts and selection notes.
- `prompts/`, `skills/`, `resources/`: agent prompts, coaching procedures and curated campus resources.
- `scripts/`, `tests/`: judging/analysis utilities and verification tests.
- `runs_corrected/2026-11-04_v3/`: submitted outputs, logs, judge scores and human ratings.

## Setup

Requires **Python >=3.15** and **uv**. Dependencies are pinned in `uv.lock`: aisuite (Gemini), pandas, PyArrow, NumPy, Pydantic, Matplotlib, SciPy, python-dotenv and tqdm.

Run commands from the repository root:

```text
uv sync --locked
```

Copy `.env.example` to `.env` without overwriting existing credentials. Set `GEMINI_API_KEY` for generation and `OPENAI_API_KEY` for judging. `GEMINI_API_KEY_FREE` is an optional second Gemini key; retries preserve the configured model.

Extract StudentLife directly under `data/`, containing `sensing/`, `EMA/response/`, `education/`, `survey/`, `call_log/` and `sms/`. The supplied archive has 49 identifiers with activity files; the published study describes 48 students over ten weeks.

## Run evaluation

New results go to **`runs_local/`**, preserving submitted runs.

### 1. Prepare features and cases (offline)

```text
uv run asl preprocess --data-dir data --out-dir cache/features
uv run asl cases --cache-dir cache/features --out-dir runs_local/inputs
```

These write feature caches and snapshot 20 cases, eight profiles and feedback scripts. Inputs include time-bounded sleep/activity/social indicators, EMA responses, academic schedules/deadlines and pre-term survey background.

### 2. Generate full-system outputs (Gemini calls)

```text
uv run asl run --config configs/2026-11-04/full-paid.toml --cases runs_local/inputs/cases.jsonl --profiles runs_local/inputs/profiles.json --cache-dir cache/features --out-root runs_local
```

Under `runs_local/full/`, the run saves `outputs.jsonl`, `calls.jsonl`, `run.log`, `failed_cases.json`, configuration/provenance snapshots and `memory/<uid>.json`. Check the completion summary and `failed_cases.json` (`[]` means no failures); individual case failures do not necessarily cause a nonzero CLI exit.

Compatible runs resume automatically; each student's cases execute chronologically. Use a new output root when changing code, inputs or settings.

### 3. Complete human ratings before automated judging

```text
uv run asl human-sheet --run-id full --cases runs_local/inputs/cases.jsonl --profiles runs_local/inputs/profiles.json --out-root runs_local --max-items 10
```

Open `runs_local/full/human_eval/blind_rating_sheet.html`. Independently rate 10 non-null messages before viewing automated scores, then save the downloaded `human_ratings.json` into that directory, replacing the blank template. At least 10 successful non-null messages are required.

### 4. Judge and analyze

```text
uv run python -B scripts/judge_corrected.py --root runs_local --runs full
uv run asl analyze --cases runs_local/inputs/cases.jsonl --out-root runs_local --fig-dir runs_local/report/figures --table-dir runs_local/report/tables
```

The judge reuses matching cached scores. The shared human/LLM rubric is [prompts/judge.md](prompts/judge.md): context awareness, goal alignment and clarity, each scored 1-5. Both receive the same frozen context and message, excluding expected labels and current feedback.

Analysis saves metrics, comparisons, figures and tables: execution success, allowed-action agreement, message quality, human/LLM mean absolute differences, preference checks, latency, calls and tokens. Latency includes coaching/tools and excludes judging.

### 5. Optional: run the required ablations

```text
uv run asl ablate --config configs/evaluation.toml --cases runs_local/inputs/cases.jsonl --profiles runs_local/inputs/profiles.json --cache-dir cache/features --out-root runs_local
uv run python -B scripts/judge_corrected.py --root runs_local --runs full single no_refl no_plan refl1 refl3 plan1 plan3 modelB
```

Then rerun the analysis command. The suite reuses a compatible full run and compares single-coach operation, reflection/planning removal, reflection/planning maxima 1/2/3, and Model B on the same 20 cases. Use the explicit configurations above; bare CLI defaults select older presets.

## Cases and simulated information

[Case definitions](cases/cases.jsonl) specify participant IDs and decision times; [selection notes](cases/selection.md) describe the coverage-based selection. All 20 decisions are at 20:00 local time for eight participants.

| Cases | Purpose |
|---|---|
| 001-005 / 006-008 | High stress/load / doing well |
| 009-010 | Unmasked observation absence after passive recording ended |
| 011-012 | Explicit synthetic modality masks |
| 013-015 / 016-018 | Two three-step preference-update episodes |
| 019-020 | Support/resource referral and recent-message restraint |

Goals, preferences, constraints, scripted replies and recent-interaction notes are explicitly labeled simulated. Feedback is deterministic, embedded in cases and released after the current action; learned rules apply only to later interactions. Profiles retain separately labeled real pre-term survey background. Campus resources are manually curated, not supplied by StudentLife.

## Model settings

| Use | Model | Settings |
|---|---|---|
| Full/structural ablations | `gemini:gemini-3.6-flash` | Temperature 0.3; Critic/Memory Manager 0.1; thinking `low`; 8,192 output-token cap |
| Model B | `gemini:gemini-3.5-flash-lite` | Same role settings |
| Independent judge | `openai:gpt-5.4-mini-2026-03-17` | Temperature 0; reasoning `none`; 2,048 completion-token cap |

The full configuration enables five interacting roles (Planner, Analyst, Writer, Critic, Memory Manager), tools, eight skills, memory, and planning/reflection maxima of two. Component switches and budgets are defined in the TOML files.

## Memory reset

Memory is stored in per-participant JSON files. To delete a local run's memory:

```text
uv run asl reset-memory --out-root runs_local --run-id full
```

Normal resume rebuilds memory from saved outputs. To regenerate from scratch, add **`--reset-memory --no-resume`** to the generation command; this replaces that local run's outputs and call traces. Use a new output root to preserve earlier results. Changed messages need matching new evaluations.

## Output JSONL fields

Each line of `outputs.jsonl` represents one participant/time case. Failed records omit `evaluation_context`.

| Fields | Meaning |
|---|---|
| `case_id`, `participant_id`, `decision_time` | Case/student identifiers and timestamp with UTC offset |
| `category`, `episode_id`, `step` | Scenario category and interaction grouping/order |
| `config_id`, `model` | Configuration and generation model |
| `status`, `error` | Execution success/failure and optional error |
| `decision`, `final_message` | `suggest`, `ask` or `none`; message is null for silence/failure |
| `expected_decision` | Manually allowed offline actions, withheld from agents/judge |
| `skill_used`, `plan` | Selected procedure and collected planning steps |
| `evidence` | Findings with `source`, `detail` and `simulated` labels |
| `evaluation_context` | Frozen observations, profile and prior interaction/preference context |
| `planning`, `reflection` | Actual round counts; reflection also contains critiques |
| `memory_updates` | Newly stored preference rules from post-action feedback |
| `trace` | LLM/tool calls, prompt/completion/total tokens, latency, per-role usage and models used |

Exclude raw data, virtual environments and generated feature caches from submission.
