# Expanded StudentLife coaching architecture

This patch connects the broader StudentLife adapters to the existing coach runner, tools, planner, coach, reviewer, single-agent baseline, evaluation context and nine required experiment configurations. It includes the earlier EMA importer fix. It does not replace model providers, credentials, rate-limit handling, memory, or evaluation metrics.

## Install

From your existing project root (back up local edits first):

```bash
cd /mnt/c/CSI4900/studentlife_coach
python3 -m zipfile -c studentlife_before_expansion.zip coach pyproject.toml
python3 -m zipfile -e /path/to/studentlife_expanded_architecture_patch.zip .
python3 -m unittest discover -s tests -v
```

If you already edited studentlife_context, back it up as well; this patch replaces that package. It also replaces coach/cli.py, runner.py, orchestrator.py, tools.py, prompts.py, ablations.py, data/importer.py and data/features.py. Extract into the project root, not dataset/. No raw data are changed. Editable or installed package users should reinstall with `python3 -m pip install -e .` so the added package is discovered.

## Architecture

1. Local adapters decode named EMA fields from the installed EMA_definition.json and summarize selected sensor streams.
2. A decision-time filter keeps only responses already submitted and completed sensor intervals. The default windows are seven elapsed days for EMA and 24 elapsed hours for sensing.
3. The preparation CLI freezes one compact context per case in JSONL. Fields include observations, evidence, missing_or_unavailable, provenance, decision_time, participant_id, status and case_id. A sidecar manifest hashes the case file, codebook and resulting contexts.
4. `coach run --contexts ...` validates the case IDs, participants, cutoff timestamps and preparation status, then supplies the same context to planning, coaching and review. The single-agent baseline sees the same context and tools.
5. Tools expose the context or selected sections. Authored skills support study planning, sleep routines and movement breaks alongside existing skills. These are deterministic retrieval functions, not extra LLM agents.
6. Final outputs retain decision, final_message, evidence and trace fields. evaluation_context includes the actual expanded input for judging. The run manifest hashes the frozen contexts; every ablation reuses the same file.

## Data used

| Input | What reaches the coach | Limits |
|---|---|---|
| EMA Sleep, Stress | Decoded duration, quality, daytime sleepiness, stress label, sleep baseline | `<3` stays censored; stress categories are not averaged |
| EMA Mood, Mood 1, Mood 2 | Current emotions and separately worded expectations | Tomorrow's expected mood is not a future observation |
| EMA Exercise, Social, Activity | Exercise/walking categories, contact count ranges, reported activity proportions | Keep ranges; no invented exact durations or contact counts |
| EMA Class, Class 2, Lab | Due-work report, workload, enjoyment, challenge, expected grade | Expected grade is not an observed final grade; dated reports can become stale |
| EMA Study Spaces | Reported productivity and noise | No room/building free text |
| EMA Behavior, Events | Decoded questionnaire answers and event intensity categories | Not diagnoses; free-text event descriptions excluded |
| EMA Dining Halls | Decoded reported meal venue categories | Does not prove meal skipping or nutritional quality |
| Sensing activity, audio | Sample classification counts | Counts are not minutes; audio opt-in |
| Sensing conversation | Merged completed interval minutes | Does not identify speakers or establish loneliness |
| Sensing phonelock, phonecharge, dark | Merged completed interval durations | Not screen-on time or sleep duration |
| Sensing GPS, Wi-Fi, Wi-Fi location, Bluetooth | Opt-in timestamped row counts only | No coordinates, identifiers, location trails or inferred relationships |
| calendar, app_usage | Coverage-only diagnostics where timestamps parse | No semantic scheduling or screen-time claims until schemas are validated |
| education/deadlines.csv | Optional assumed known syllabus | OFF by default; explicit simulation assumption required |

Not yet interpreted: PAM, survey instruments, education grades/GPA, raw dinning files, call_log, sms, QR codes, free-text comments and campus-event questionnaires. These require local schemas and timing rules. Directory names alone are not enough to add reliable features. Coarse meal locations are available through the defined Dining Halls EMA instead.

## First run on real participants

Create cases using real EMA response dates. This helper chooses 09:00 America/New_York on the following day and labels generic profiles as simulated. Review/edit those profiles and any supplied history before evaluation. It does not infer user preferences from sensors.

```bash
python3 tools/build_studentlife_cases.py \
  --root dataset --participants u00 u01 u02 \
  --limit 16 --out data/cases.real.jsonl

python3 -m studentlife_context.cli \
  --dataset dataset --cases data/cases.real.jsonl \
  --sensing-streams activity,conversation,phonelock,phonecharge,dark,audio \
  --out data/contexts.real.jsonl

python3 -m coach run \
  --config configs/full.json \
  --cases data/cases.real.jsonl \
  --contexts data/contexts.real.jsonl \
  --out runs/expanded_real_01
```

Context preparation uses no model API calls. Unknown nonempty EMA codes and unreadable selected files fail visibly. Null-only answers are excluded rather than guessed. The contexts file records quality counts and error status; the CLI exits unsuccessfully if any case fails. Choose a new output context filename for each preparation attempt. Never run failed contexts.

The normalized four-stream observations file is optional in this route. If supplied with --observations, it is included alongside the expanded context. Without --contexts, the existing demo defaults continue to work. Do not use demo participant IDs with real contexts. The mock model tests plumbing only; its heuristic behavior does not evaluate expanded coaching quality.

## Required comparisons

With MODEL_B_PROVIDER and MODEL_B already configured in your .env:

```bash
python3 -m coach ablations \
  --config configs/full.json \
  --cases data/cases.real.jsonl \
  --contexts data/contexts.real.jsonl \
  --out runs/expanded_ablations_01
```

This preserves the nine existing configurations, including single/multi-agent, no reflection/planning, reflection/planning depth budgets and model B. No extra LLM stage or obligatory call was added. More context can increase input tokens per request. Use existing judge/human-review/report commands after runs; mock results are not coursework evidence of model quality.

Optional data-source experiments should use separate frozen context files, separate run folders, and the same cases, profile/history, model and system settings. For example, `--include ema` prepares EMA-only evidence. This is a separate comparison from the mandatory system ablations.

## Diagnostics and limitations

```bash
python3 -m studentlife_context.inspect \
  --dataset dataset --participant u00 \
  --out outputs/schema_u00.json
```

This inventory prints field names and row counts rather than values. It currently recognizes CSV, JSON and JSONL participant-named files; unrecognized text files and shared tables need separate schema inspection.

The preparation code scans selected files per case. Preparing many cases over high-frequency sensing can take time; frozen contexts avoid repeating that work for each ablation but do not provide an indexed database. Start with 16 cases. Additional sensors can be selected using --sensing-streams; more coverage-only data is not necessarily better coaching evidence.

Sensors use measurement time or completed interval end as assumed availability because upload timestamps are unavailable. Document this offline simulation assumption. EMA uses resp_time. Future-record and invalid-record diagnostics are removed before context enters agent prompts, so future participation counts cannot leak. Source file existence/missingness still reflects the released offline dataset, not a live collection system.

Conditional EMA intensity/duration questions require the corresponding parent answer in the same response. Sleep.social means daytime sleepiness. The EMA summary preserves the questionnaire text, source, code, decoded label, timestamp, age, category counts and up to four recent responses per field. Personal sleep baseline uses earlier exact durations and excludes the latest answer. Unknown codes fail rather than being silently converted to numbers.

The adapters build on the provided EMA definitions and original StudentLife documentation: https://studentlife.cs.dartmouth.edu/dataset.html . Sensor code labels should be checked if using a modified dataset release. No model is trained on future outcomes and no predictive stress model is claimed.

Validation performed here: 42 unit tests passed, including identical context delivery across all nine configurations, conditional questionnaire handling, unknown-code errors, malformed-file failures, cutoff/identity checks and exclusion of future diagnostics. An end-to-end synthetic case-generation → context-preparation → coach CLI run passed with a mock model. Your full local archive and live cloud models were not available for this validation.
