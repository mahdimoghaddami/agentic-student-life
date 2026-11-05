# Multi-Agent StudentLife Stress Coach

**Authors:** Mahdi Moghaddami and **Brett Piggott**

**Course:** CSI 4900/5900 Agentic AI, Oakland University, Fall 2026

[Research paper (PDF)](output/pdf/studentlife_coach_paper/studentlife_coach.pdf) · [LaTeX source](output/pdf/studentlife_coach_paper/studentlife_coach.tex) · [Project requirements](project_doc.pdf)

The coach uses historical StudentLife observations, a clearly labeled simulated student profile, and earlier interactions to choose `suggest`, `ask`, or `none`. A sent message is a brief supportive suggestion or clarifying question; deliberate silence has `final_message: null`. This is an offline simulation, with no model training or fine-tuning.

The published study describes 48 students over a ten-week term. The supplied archive has **49 identifiers with activity files**; preprocessing covers those 49 identifiers. Evaluation uses **20 cases from eight identifiers**, not 49 complete student records at every time point.

## 1. Repository structure

```text
src/agentic_student_life/
  cli.py                  CLI commands
  config.py               TOML loaders and component controls
  orchestrator.py         Role coordination, chronological execution, resume
  llm.py, budget.py       Model transport, retries, token/cost accounting
  provenance.py           Configuration/source/data fingerprints
  data/                   StudentLife loaders, feature engineering, bounded views
  agents/                 Planner, Analyst, Writer, Critic, Memory Manager, baseline
  tools/                  Read-only sensing, academic and resource tools
  memory/                 Per-participant JSON episodes and learned preferences
  skills/                 Markdown skill index and loader
  cases/                  Deterministic case and simulated-profile builders
  eval/                   Judge, human sheets, metrics, plots and tables
configs/
  evaluation.toml         Current nine-condition suite; matches dated presets
  2026-11-04/             Exact individual model/configuration presets
cases/                    Case definitions, profiles, feedback, selection notes
prompts/                  Role prompts and complete judge rubric
skills/                   Eight reusable coaching procedures
resources/                Curated campus-resource catalogue
scripts/                  Experiment, judging, analysis and paper-asset scripts
tests/                    Offline regressions and data-dependent leakage checks
runs_corrected/2026-11-04_v3/  Saved evaluated suite and human ratings
output/pdf/studentlife_coach_paper/  Final paper, source and figure assets
```

`runs/` and the other dated directories under `runs_corrected/` are archived evidence. The commands below write new evaluations to **`runs_local/`**, leaving those archives alone. Run every command from the repository root. The Python/uv commands work in PowerShell or a POSIX shell.

## 2. Dependencies, credentials and dataset

The project requires **Python >=3.15** and **uv**. The lockfile pins the tested environment; `pyproject.toml` lists `aisuite[gemini]`, pandas, PyArrow, NumPy, Pydantic, Matplotlib, SciPy, python-dotenv and tqdm. The specialized OpenAI judging script uses Python's standard-library HTTP client, so an additional OpenAI SDK is unnecessary. A LaTeX installation with TikZ and `latexmk` is needed only to rebuild the PDF.

```text
uv sync --locked
uv run asl --help
```

Create `.env` from the template without replacing an existing file:

```text
uv run python -c "from pathlib import Path; p=Path('.env'); p.exists() or p.write_bytes(Path('.env.example').read_bytes())"
```

Edit `.env` locally:

```dotenv
GEMINI_API_KEY=your_primary_google_key
GEMINI_API_KEY_FREE=your_optional_second_google_key
OPENAI_API_KEY=your_openai_judge_key
```

At least one Gemini key is needed for generation. The optional second key is tried on eligible quota/transient failures; retries keep the configured model. OpenAI credentials are needed only for judging. Offline analysis, preprocessing and tests do not require API credentials. Budget ledgers estimate usage from the configured prices and reserve for uncertain failures; they do not read account balances. Generation limits in the presets are **per run**, not a shared cap for a new nine-condition suite. The judge script has a shared $2 estimated-usage limit within its output root. Preset prices are the experiment's accounting assumptions, not a promise about future billing.

Download/extract the StudentLife archive specified in the assignment. Its contents must be directly under `data/`, not nested in an extra `dataset/` directory:

```text
data/
  sensing/activity/activity_u00.csv   # and other participant/modality files
  sensing/dark/                      # sleep-inference inputs
  sensing/phonelock/
  sensing/phonecharge/
  sensing/conversation/
  EMA/response/                      # Stress, Sleep, Exercise, Social, etc.
  education/class_info.json          # plus course/deadline files
  survey/                            # pre-term psychological/personality surveys
  call_log/
  sms/
```

The implementation uses inferred sleep, activity, conversations, phone-event counts, EMA stress/mood/sleep/exercise/social responses and comments, academic schedules/deadlines, and pre-term PSS, PHQ-9, loneliness and Big Five background. It excludes grades/GPA, Piazza and post-term surveys. Daily features precede the decision date; the same-day last-night sleep estimate is available only after noon. EMA timestamps must be at or before the decision, and memory must be strictly earlier. Upcoming syllabus deadlines are assumed known calendar information. Term-phase labels are week-based heuristics. Missing observations remain missing.

## 3. Run the full evaluation and save outputs/logs

### Prepare features and input snapshots (offline)

```text
uv run asl preprocess --data-dir data --out-dir cache/features
uv run asl cases --cache-dir cache/features --out-dir runs_local/inputs
```

Preprocessing writes `daily_<uid>.parquet`, `ema_<uid>.parquet`, `academic.json` and `surveys.json`. The second command writes **20 cases**, **eight simulated profiles**, and `feedback_scripts.json` to `runs_local/inputs/`. It does not generate `selection.md`; the repository's selection notes are separately maintained. Repeat input generation only when intentionally preparing that input set; use a different output root for different experiments.

### Generate the 20 full-system cases (Gemini API calls)

```text
uv run asl run --config configs/2026-11-04/full-paid.toml --cases runs_local/inputs/cases.jsonl --profiles runs_local/inputs/profiles.json --cache-dir cache/features --out-root runs_local
```

The `full-paid.toml` filename identifies the exact paced preset used for the reported full configuration; it does not itself enable billing on a Google account. Successful API access to the configured model is required.

The run writes:

| Path under `runs_local/full/` | Contents |
|---|---|
| `outputs.jsonl` | One final record per selected case, including failed cases |
| `calls.jsonl` | Recorded LLM-turn/tool-count, token, latency and preview traces |
| `run.log` | Case start/completion, decisions, failures and resume skips |
| `failed_cases.json` | Failure details; `[]` when all cases succeed |
| `config.snapshot.toml`, `manifest.json` | Exact settings and source/data/input fingerprints |
| `api_usage.jsonl` | Estimated provider usage/reservations for budgeted generation |
| `memory/<uid>.json` | Profile, earlier episodes and learned preference rules |

Inspect the printed completion summary and `failed_cases.json`; the CLI reports case failures in those records rather than guaranteeing a nonzero process exit for each failed case. A failed execution is distinct from a successful `none` action.

Compatible reruns resume by default, making no new generation calls for a completed chronological prefix. An earlier missing/failed case causes its later same-student suffix to run again because its memory can change. Each student's cases run chronologically across episode IDs; different students may run concurrently. A changed configuration, source, data or input fingerprint rejects resume. Use a new output root for changed experiments.

### Export and complete 10 independent human ratings

```text
uv run asl human-sheet --run-id full --cases runs_local/inputs/cases.jsonl --profiles runs_local/inputs/profiles.json --out-root runs_local --max-items 10
```

Open `runs_local/full/human_eval/blind_rating_sheet.html`, rate each message on the full displayed rubric **before viewing automated scores**, and use its Save button. Place the downloaded `human_ratings.json` in that same `human_eval/` directory, replacing the blank template. CSV and JSON templates are also exported. Export requires at least 10 successful non-null messages; silence cannot be rated as a message. Existing ratings are preserved on a matching export and rejected if the selected message/context fingerprints differ. New generations require matching new human ratings.

### Judge saved messages (OpenAI API calls only for uncached items)

```text
uv run python -B scripts/judge_corrected.py --root runs_local --runs full
```

Use this specialized entry point for the reported OpenAI settings. It reads `inputs/cases.jsonl`, `inputs/profiles.json` and saved outputs, writes `judge_scores.jsonl` under each selected run, and records shared estimates in `runs_local/judge_api_usage.jsonl`. Despite its filename, `--root` accepts a new evaluation root. It never regenerates coach messages. Cached scores are reused only when message/context, rubric, model and temperature fingerprints match. The script checks for `OPENAI_API_KEY` even if all scores are cached.

The complete evaluation prompt and anchored rubric are in [prompts/judge.md](prompts/judge.md). Human and LLM evaluators receive the same frozen `evaluation_context`, decision and final message, excluding expected labels, rationales and current feedback. The saved packet contains deterministic default-window summaries; it may omit dynamically retrieved windows, resource results and full skill documents seen during generation. This limits claims of exact information equivalence.

### Analyze the new outputs (offline)

```text
uv run asl analyze --cases runs_local/inputs/cases.jsonl --out-root runs_local --fig-dir runs_local/report/figures --table-dir runs_local/report/tables
```

This writes `runs_local/summary_metrics.json`, `matched_comparisons.json`, PDF/PNG figures and LaTeX tables. It measures execution success, agreement with manually allowed actions, non-null-message rubric scores, prior-feedback preference checks, human/LLM mean absolute differences, and per-case latency/calls/tokens. Latency includes tools and all coaching model steps, including post-action preference extraction, and excludes judging. Preference checks are a lexical proxy with possible false positives; action labels are authored references, not measured student outcomes. The generic matched-comparison JSON retains a conservative legacy-interpretation note; it is not a statistical causal test.

## 4. Ablations, controls and custom inputs

### Run all nine current conditions

After preparing inputs as above:

```text
uv run asl ablate --config configs/evaluation.toml --cases runs_local/inputs/cases.jsonl --profiles runs_local/inputs/profiles.json --cache-dir cache/features --out-root runs_local
```

This resumes a compatible `full` run and executes the other conditions in isolated directories: `single`, `no_refl`, `no_plan`, `refl1`, `refl3`, `plan1`, `plan3`, `modelB`. All use the same 20 case definitions. The consolidated coach keeps the same baseline inputs, tools, skills and memory policy, but retains auxiliary post-feedback extraction. Histories can diverge as each condition generates its own earlier messages/rules. Its tool loop permits seven turns versus five for the multi-agent Analyst/Writer loops; this is not an identical-compute comparison.

To judge the complete suite, use the following **instead of** the full-only judge command, or run it afterward to reuse matching full scores:

```text
uv run python -B scripts/judge_corrected.py --root runs_local --runs full single no_refl no_plan refl1 refl3 plan1 plan3 modelB
```

Then rerun the analysis command. `asl ablate --only no_refl,plan1` limits generation to named conditions when supplied with the same explicit `--config`, cases, profiles, cache and output-root options above. Do not use bare `asl run`, `asl ablate` or `asl judge` to reproduce the reported settings: their older default configuration files use different models/transports.

| Required pattern / component | Control | Full behavior and disabled behavior |
|---|---|---|
| Multi-agent system | `system.mode` | `multi_agent`: Planner, Analyst, Writer, Critic and Memory Manager. `single_agent`: consolidate online reasoning/writing; auxiliary feedback extraction remains. |
| Planning | `planning.enabled`, `max_rounds` | On, maximum 2 actual Planner calls. Off: Analyst gathers evidence, Writer chooses action/skill. At depth 1, Analyst runs before the single Planner call. |
| Tool use | `tools.enabled`, `max_turns` | On, 5 model turns per Analyst/Writer loop. Off removes autonomous Analyst data queries and provides a fixed summary; skill loading is controlled separately. Single-coach tool access is disabled by this flag. |
| Reflection | `reflection.enabled`, `max_rounds` | On, maximum 2 Critic review/revision cycles, with early approval. Off omits Critic calls. A final budget-limited revision need not receive another review. |
| Memory | `memory.enabled`, `history_k` | On, 5 recent episodes plus prior learned rules. Off removes earlier episodes/rules from prompts and skips rule extraction; the initial profile remains and episodes may still be logged. |
| Skills | `skills.enabled` | On, 8 Markdown procedures. Off removes the index/documents/loading access and uses generic supportive instructions. |

The Analyst can call `get_time_context`, `get_sleep_summary`, `get_activity_summary`, `get_social_summary`, `get_stress_mood_history`, `get_academic_load`, `compare_to_baseline`, and `search_campus_resources`. The Writer can use `load_skill`; the consolidated coach can also use `recall_memory`. Planner/Critic/Memory Manager use supplied structured context rather than an autonomous data-tool loop.

The skills are `micro_study_break`, `sleep_hygiene_nudge`, `gentle_movement`, `social_reconnection`, `deadline_chunking`, `campus_resource_referral`, `clarifying_question`, and `positive_reinforcement`. Resources are a manually curated catalogue in `resources/campus_resources.json`, not a StudentLife modality or live lookup.

### Choose particular cases and settings

Create a configuration from the full preset, retaining its model/budget settings while selecting a preference interaction and its preceding feedback step:

```text
uv run python -c "from pathlib import Path; from agentic_student_life.config import load_run_config; c=load_run_config('configs/2026-11-04/full-paid.toml'); c.config_id='custom'; c.case_ids=['case_013','case_014']; Path('configs/custom.toml').write_text(c.to_toml(), encoding='utf-8')"
uv run asl run --config configs/custom.toml --cases runs_local/inputs/cases.jsonl --profiles runs_local/inputs/profiles.json --cache-dir cache/features --out-root runs_local
```

Edit that TOML to change the model or component controls, using a new run ID/output root for changed settings. For a single independent case, set only its ID. Running `case_014` alone does not replay `case_013`; include earlier cases when their feedback should be learned. To define a new participant/time input, supply a JSONL file with unique `case_id`, `participant_id`, `decision_time` and any optional `mask`/simulated interaction fields, plus a matching profile JSON and feature files for that participant. Pass those files through `--cases` and `--profiles`. Expected actions are optional offline labels and never answers given to the coach.

## 5. Memory reset and validation

Memory uses plain per-participant **JSON files**, containing the simulated baseline profile, episodes, learned preferences and provenance timestamps/case IDs. There is no SQL/vector/graph database. Scripted feedback is deterministic and is released after the current action; it is not random or LLM-generated. Learned rules are available only to later decisions.

To delete memory for a local run:

```text
uv run asl reset-memory --out-root runs_local --run-id full
```

This removes only `runs_local/full/memory/`. A normal resume reconstructs memory from saved outputs. To actually regenerate that local run from an empty history, the following intentionally replaces its outputs/call traces and rebuilds its memory:

```text
uv run asl run --config configs/2026-11-04/full-paid.toml --cases runs_local/inputs/cases.jsonl --profiles runs_local/inputs/profiles.json --cache-dir cache/features --out-root runs_local --reset-memory --no-resume
```

Prefer a new output root to retain the prior local experiment. Regenerated messages need new matching judge scores and human ratings.

Run verification without model API calls:

```text
uv run python -B -m unittest discover -s tests -v
uv run python -B tests/test_leakage.py
```

The unittest suite uses synthetic fixtures and mocked model responses. The separate leakage command requires `cache/features/` from preprocessing and checks raw-data temporal bounds, invariance to future observations, masks and output sizes. Local README verification also exercises preprocessing/case generation and the CLI generation/resume, human-sheet, judge, analysis and reset paths in disposable directories with blocked network access and mocked model responses. On November 4, 2026, dependency synchronization, all 49 participants' preprocessing, 31 regression tests, five leakage checks, and this isolated CLI integration check passed. This verifies command integration; it does not establish future provider availability or new message quality.

## 6. Evaluation cases and simulation labels

The 20 cases use `u59`, `u08`, `u19`, `u10`, `u57`, `u16`, `u00` and `u02`, all at 20:00 `America/New_York`. Coverage-based selection is deterministic, not random sampling. The authoritative case definitions are [cases/cases.jsonl](cases/cases.jsonl); [selection.md](cases/selection.md) provides contextual selection notes whose numeric rationales are not recomputed by the case builder.

| Cases | Coverage |
|---|---|
| 001-005 | Typical high stress/academic load |
| 006-008 | Doing well; appropriate restraint |
| 009-010 | Unmasked observation absence after passive sensing ended May 31; June 10 for `u00` and June 6 for `u57`, not demonstrated in-term device failures |
| 011-012 | Explicit synthetic modality masks (`mask_simulated: true`) |
| 013-015, 016-018 | Two three-step simulated preference/feedback episodes |
| 019-020 | Support/resource and recent-message restraint scenarios |

Goals, tone/activity preferences and constraints are labeled simulated in `profiles.json`, with real pre-term survey background labeled separately. Scripted replies and recent-interaction notes are labeled simulated; feedback scripts are also exported in `feedback_scripts.json`. The runtime reads replies embedded in each case; editing only the separate feedback file does not change runtime replies. Sensing/EMA values remain dataset observations/inferences rather than invented student responses. Historical survey scores are not current diagnoses. Campus-resource entries are static curated information, not verified availability at each historical decision date.

## 7. Models and generation settings

| Use | Exact provider/model | Settings |
|---|---|---|
| Full and structural ablations | `gemini:gemini-3.6-flash` | Temperature 0.3, except Critic/Memory Manager 0.1; thinking `low`; 8,192 output-token cap |
| Model B, same full architecture | `gemini:gemini-3.5-flash-lite` | Same role temperatures, thinking and output cap |
| Independent judge | `openai:gpt-5.4-mini-2026-03-17` | Temperature 0, reasoning `none`, 2,048 completion-token cap, structured rubric response |

The generation presets use four workers across independent student histories and one-second request spacing per credential. The judge uses two workers. Planning/reflection limits are maxima, not forced realized depths. `configs/evaluation.toml` matches the dated individual presets, including their estimated-usage allocations. The specialized judge script enforces transport settings beyond the basic `JudgeConfig` fields.

## 8. Output JSONL schema

Each line of `<out-root>/<config_id>/outputs.jsonl` represents one participant/time case. Successful records have these 21 fields; failed records omit `evaluation_context`.

| Field | Type | Meaning |
|---|---|---|
| `case_id` | string | Unique evaluation identifier |
| `participant_id` | string | StudentLife identifier |
| `decision_time` | ISO timestamp | Localized decision time with UTC offset |
| `category` | string | Offline scenario category |
| `episode_id` | string | Declared episode group; chronological memory can span groups for the same student |
| `step` | integer | Position within the declared episode |
| `config_id` | string | Run/configuration identifier |
| `model` | string | Configured generation provider/model |
| `status` | string | `ok` or `failed` |
| `error` | string/null | Failure description or null |
| `decision` | string | `suggest`, `ask` or `none`; check `status` to distinguish failure from silence |
| `expected_decision` | string list | Manually allowed offline actions, not empirical ground truth; withheld from agents/judge |
| `skill_used` | string/null | Selected coaching procedure, null for silence |
| `plan` | string list | Collected planning steps, or consolidated coach's stated checks |
| `evidence` | object list | Source-tagged findings with `source`, `detail`, `simulated` |
| `evaluation_context` | object | Frozen observations, simulated profile, prior rules/interactions and labeled interaction note; excludes expected labels and current feedback |
| `final_message` | string/null | Final suggestion/question, or null for silence/failure |
| `reflection` | object | `rounds_used` and collected critique/verdict strings |
| `planning` | object | `rounds_used`: actual Planner invocations |
| `memory_updates` | string list | Newly stored preference rules from post-action feedback |
| `trace` | object | `llm_calls`, `tool_calls`, prompt/completion/total tokens, `latency_s`, `per_agent`, `models_used`; total tokens may include reasoning beyond visible completion text |

## 9. Saved results, paper and submission

The completed evaluated suite is under [runs_corrected/2026-11-04_v3/](runs_corrected/2026-11-04_v3/): nine conditions, **180 valid final outputs**, **140 non-null messages judged**, and **10 independent human ratings**. The full configuration has 20/20 allowed decisions and mean message quality 4.81/5; human/LLM criterion MAD is 0.267 across 30 ratings. These are descriptive results for selected offline cases, not clinical or population-effectiveness claims.

- [Comparison CSV](runs_corrected/2026-11-04_v3/comparison.csv)
- [Detailed metrics and human comparison](runs_corrected/2026-11-04_v3/summary_metrics.json)
- [Execution/accounting summary](runs_corrected/2026-11-04_v3/execution_summary.json)
- [Completed human ratings](runs_corrected/2026-11-04_v3/full/human_eval/human_ratings.json)

Reported planning-three efficiency includes recovery accounting in `plan3/recovery_info.json`; generic analysis of final outputs alone does not include archived failed/dependent attempts. `scripts/analyze_corrected.py` is the dedicated offline reanalysis entry point for that saved suite, including provenance checks and recovery adjustments. `scripts/run_corrected_ablations.py` is an archival resume utility, not the fresh-run entry point; it rejects a changed source fingerprint, including the shared call-log write lock added during command verification. The logging fix does not change existing messages or ratings, but strict resume compatibility still requires the original source. The archived inputs, outputs and ratings need not be regenerated to inspect the submitted results.

Rebuild the final research paper from saved evidence without model calls:

```text
uv run python -B scripts/build_research_paper_assets.py
latexmk -pdf -interaction=nonstopmode -halt-on-error -cd output/pdf/studentlife_coach_paper/studentlife_coach.tex
```

The paper has 10 main pages, one reference page and three appendix pages. For submission, include the source/configurations/prompts/skills/resources, dependency lockfile, README, PDF report, case definitions and labeled profiles/feedback, final JSONL outputs, execution logs and evaluation materials needed to reproduce the results. Use a ZIP name such as `groupXX_moghaddami_piggott.zip` with the actual group number. Exclude raw `data/`, virtual environments, generated feature caches, temporary verification files and model weights, as required by the assignment.
