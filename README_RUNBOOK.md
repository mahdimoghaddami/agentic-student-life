# StudentLife coach: commands, automatic keys, and submission workflow

This guide applies AFTER the expanded architecture patch. This package includes the grounding fix, automatic key failover, experiment-configuration generation, model connectivity checks and run auditing. It does not contain API keys or claim that live experiments/human ratings have been completed.

## 1. Install and validate

```bash
cd /mnt/c/CSI4900/studentlife_coach
source .venv/bin/activate
python3 -m zipfile -c studentlife_before_autokeys.zip coach tools
python3 -m zipfile -e /path/to/studentlife_autokeys_runbook.zip .
python3 -m pip install -e '.[plots]'
python3 -m unittest discover -s tests -v
```

Back up local edits first. Existing dataset files, contexts, results and .env are preserved. Never put your populated .env in the submitted ZIP. Use fresh run directories; the runner refuses to overwrite a nonempty directory. Tests use synthetic/local/mocked endpoints and spend no cloud credits.

## 2. Configure automatic keys and two actual models

Edit EXISTING assignments in .env rather than appending duplicates. Existing shell environment variables override .env; unset stale exported variables if needed. Merge AUTO_KEYS.env.example into .env and replace all placeholders locally:

```dotenv
COACH_PROVIDER=gemini
GEMINI_MODEL=gemini-3.5-flash-lite
GEMINI_KEY_MODE=auto
GEMINI_API_KEY_1=YOUR_FIRST_KEY
GEMINI_API_KEY_2=YOUR_SECOND_KEY
GEMINI_MIN_INTERVAL_SECONDS=6
GEMINI_MAX_RETRIES=2
GEMINI_MAX_RETRY_WAIT_SECONDS=120
GEMINI_RETRY_BASE_SECONDS=15
REQUEST_TIMEOUT=300
MODEL_B_PROVIDER=gemini
MODEL_B=gemini-3.1-flash-lite
JUDGE_PROVIDER=gemini
JUDGE_MODEL=gemini-3.5-flash-lite
```

The two model IDs are documented by Google; account access/quota must still be checked. Use the stable 3.1 Flash-Lite ID, not the retired preview ID. Sources: https://ai.google.dev/gemini-api/docs/models and https://ai.google.dev/gemini-api/docs/gemini-3 . The judge uses separate scoring calls; choosing the same model family as the coach is a limitation to report, not independent-vendor validation.

Key behavior:
- Keys are sorted by numerical suffix (_1, _2, _10); gaps and any positive suffix are supported. The legacy unnumbered key is appended. Duplicate secret values are tried only once.
- A working key remains selected. On 401/403, 429 or eligible server errors, the pool advances cyclically to the next eligible key. The model itself NEVER changes during failover.
- Rate-limited keys cool down; Retry-After is honored. Daily/billing-exhausted quota groups are parked for the rest of the process. 401/403 keys are disabled for that process. Invalid model/request errors, malformed outputs and ambiguous network failures are surfaced rather than blindly cycling.
- When all keys are cooling down, the pool waits within GEMINI_MAX_RETRY_WAIT_SECONDS (a cumulative cooldown-wait budget per logical call). Attempts are capped at number_of_unique_keys × (GEMINI_MAX_RETRIES + 1). Requests still use per-model global pacing; failover does not remove spacing.
- If none can serve the request within the budget, the case fails visibly. Every attempted HTTP call remains in traces, with credential NAME only. Unknown token usage on failed attempts is not fabricated.
- State is shared across agents/cases in ONE sequential Python process. It resets on a new process and does not coordinate separate terminals. Run experiments sequentially. Different models have separate cooldown scopes.
- Auto mode ignores GEMINI_KEY_SLOT. To restore manual behavior, set GEMINI_KEY_MODE=manual and select the slot as before.

Google quotas are PER PROJECT, not per API key: https://ai.google.dev/gemini-api/docs/rate-limits . Multiple keys from the same project do not multiply quota. Add project IDs when known:

```dotenv
GEMINI_PROJECT_ID_1=actual-project-id
GEMINI_PROJECT_ID_2=actual-project-id
```

Use the same label for keys in the same project. A quota cooldown then applies to both. Without labels, the program cannot discover shared project quotas and may receive one failure for each key before stopping. This is bounded failover, not unlimited capacity.

## 3. Freeze configs and check both models

```bash
python3 tools/setup_experiments.py --base configs/full.json --out configs/study
python3 tools/check_models.py --configs configs/study --out runs/model_check.json
```

Config generation uses no API calls. Connectivity checking makes a small real request to each model, with bounded failover if needed. Stop if either fails. This checks access and response format, NOT architecture quality. Full model-B testing is in sections 6–7. The model-B config differs from full ONLY in name/provider/model; temperature, tools, memory, skills and planning/reflection budgets are identical.

Configuration generation resolves and freezes .env model names. If you change models later, generate into a new config directory. It rejects identical A/B model IDs. It also writes optional no_tools, no_memory and no_skills configs.

## 4. Select and prepare evaluation cases

Your existing data/cases.real.jsonl and data/contexts.real.jsonl are usable without regenerating them. The current 16 cases cover three participants in an early period: a pilot, not a representative ten-week cohort. Document the participants, dates, selection rule and missingness. No required sample count beyond the human-rating requirement was stated in the assignment.

For a larger cohort, choose participants and case count BEFORE seeing outputs, for example:

```bash
python3 tools/build_studentlife_cases.py --root dataset \
  --participants u00 u01 u02 u03 u04 --limit 100 --out data/cases.study.jsonl
python3 -m studentlife_context.cli --dataset dataset \
  --cases data/cases.study.jsonl \
  --sensing-streams activity,conversation,phonelock,phonecharge,dark,audio \
  --out data/contexts.study.jsonl
```

The helper selects chronologically, using 09:00 New York on the day after EMA responses; it does not stratify across the entire term. Change/review selection if broader temporal coverage is intended. Preparation uses no model API calls. Unknown codes fail visibly. Raw data remain unmodified. For commands below using your CURRENT prepared cohort, filenames remain cases.real/contexts.real.

Add reproducible, clearly simulated preference changes and feedback to the real-data cases:

```bash
python3 tools/add_simulated_history.py \
  --cases data/cases.real.jsonl --out data/cases.personalized.jsonl
```

This preserves IDs/times, so existing contexts still match. It adds a goal, an initial quiet-break preference, a later stretching preference, and later rejection of a simulated break suggestion. All invented information is labeled simulated_profile or simulated_interaction. Review these inputs. The same supplied histories are used in EVERY controlled configuration. Outputs are isolated by case for the main ablations; supplied history is the controlled history, not output generated by a different configuration.

To quantify decision appropriateness, manually annotate acceptable_decisions in the selected case file BEFORE viewing outputs, using the available context and a documented criterion. Allowed labels are suggest, clarify, no_message; more than one may be reasonable. Empty lists produce no decision-appropriateness score, rather than fabricated accuracy. Do not set all labels acceptable merely to obtain a high score. Context files do not contain these evaluation labels, and agents do not receive them.

## 5. Full-system pilot and design-pattern audit

```bash
python3 -m coach run --config configs/study/full.json \
  --cases data/cases.personalized.jsonl --contexts data/contexts.real.jsonl \
  --out runs/personalized_pilot_01
python3 tools/audit_run.py --run runs/personalized_pilot_01
```

The updated prompt asks agents to consult a relevant evidence/preference tool and coaching skill when enabled. Actual calls are model-dependent; inspect tool_calls in the audit and traces. Do not report tool use merely because tools were available. The audit also reports histories, actual planning/reflection counts, failed cases and non-null messages. A no_message decision can be appropriate; do not force messages just to reach ten ratings.

Review representative messages and check preference changes, missing-data behavior, citations and temporal grounding before spending on all configurations. If requirements are not visibly demonstrated, revise cases/workflow and run consistently before final evaluation.

## 6. All nine required configurations in ONE command

```bash
python3 -m coach ablations --config configs/study/full.json \
  --cases data/cases.personalized.jsonl --contexts data/contexts.real.jsonl \
  --model-b-provider gemini --model-b gemini-3.1-flash-lite \
  --repeats 1 --out runs/study
```

This produces full_rep1, single_rep1, no_reflection_rep1, no_planning_rep1, reflection_2_rep1, reflection_3_rep1, planning_2_rep1, planning_3_rep1 and model_b_rep1. Do not run section 7 as well unless intentionally repeating the study in new folders. This command includes the second-model architecture comparison, not just a connectivity test.

## 7. Each run separately (alternative to section 6)

Use these to control when each experiment runs. All use the same cases/context. Run sequentially, and use fresh directories if rerunning.

```bash
# Full: multi-agent, planning 1, reflection 1, model A
python3 -m coach run --config configs/study/full.json --cases data/cases.personalized.jsonl --contexts data/contexts.real.jsonl --out runs/study/full_rep1

# Single-agent baseline; identical input/tools/budgets
python3 -m coach run --config configs/study/single.json --cases data/cases.personalized.jsonl --contexts data/contexts.real.jsonl --out runs/study/single_rep1

# Reflection off
python3 -m coach run --config configs/study/no_reflection.json --cases data/cases.personalized.jsonl --contexts data/contexts.real.jsonl --out runs/study/no_reflection_rep1

# Planning off
python3 -m coach run --config configs/study/no_planning.json --cases data/cases.personalized.jsonl --contexts data/contexts.real.jsonl --out runs/study/no_planning_rep1

# Reflection depth 2 and 3; full supplies depth 1
python3 -m coach run --config configs/study/reflection_2.json --cases data/cases.personalized.jsonl --contexts data/contexts.real.jsonl --out runs/study/reflection_2_rep1
python3 -m coach run --config configs/study/reflection_3.json --cases data/cases.personalized.jsonl --contexts data/contexts.real.jsonl --out runs/study/reflection_3_rep1

# Planning depth 2 and 3; full supplies depth 1
python3 -m coach run --config configs/study/planning_2.json --cases data/cases.personalized.jsonl --contexts data/contexts.real.jsonl --out runs/study/planning_2_rep1
python3 -m coach run --config configs/study/planning_3.json --cases data/cases.personalized.jsonl --contexts data/contexts.real.jsonl --out runs/study/planning_3_rep1

# Model B under the same full-system settings
python3 -m coach run --config configs/study/model_b.json --cases data/cases.personalized.jsonl --contexts data/contexts.real.jsonl --out runs/study/model_b_rep1
```

Depths are MAXIMUM budgets; stages may stop early. Report actual counts from traces alongside maxima. The final full system retains Planner, Coach and Reviewer. The single-agent ablation uses a unified role with its working history. Grounding checks apply across every variant; no-reflection has no hidden repair call. Separate deterministic grounding issues from issues independently discovered by the reviewer.

Optional component ablations:

```bash
python3 -m coach run --config configs/study/no_tools.json --cases data/cases.personalized.jsonl --contexts data/contexts.real.jsonl --out runs/optional/no_tools
python3 -m coach run --config configs/study/no_memory.json --cases data/cases.personalized.jsonl --contexts data/contexts.real.jsonl --out runs/optional/no_memory
python3 -m coach run --config configs/study/no_skills.json --cases data/cases.personalized.jsonl --contexts data/contexts.real.jsonl --out runs/optional/no_skills
```

## 8. Missing-data and persistent-memory demonstrations

These existing fixtures are SYNTHETIC and must be reported separately from real StudentLife evidence. With live models they demonstrate behavior; with mock they test plumbing only.

```bash
# Typical/missing-data/preference fixtures
python3 -m coach run --config configs/study/full.json --cases examples/cases.jsonl --observations examples/observations.jsonl --out runs/demos/fixtures

# Sequential memory: prior generated outputs persist; later simulated feedback updates preferences
python3 -m coach run --config configs/study/full.json --cases examples/episodes.jsonl --observations examples/observations.jsonl --episodes --out runs/demos/memory
python3 tools/audit_run.py --run runs/demos/memory
```

Memory reset: each fresh output directory creates a fresh memory.sqlite. Normal runs isolate each case; --episodes shares memory within an episode and sorts decision times. Do not delete old databases to reuse a nonempty result folder. Use a new directory for every independent comparison. Episode outputs are configuration-dependent histories; keep them separate from the identical-history primary ablations.

## 9. Human ratings BEFORE viewing judge scores

```bash
python3 -m coach human-export \
  --outputs runs/study/full_rep1/outputs.jsonl --n 10 \
  --out evaluations/human_full
```

Complete evaluations/human_full/ratings.csv independently using RUBRIC.txt: context awareness, goal alignment and clarity, each 1–5. Fill notes, rated_at (ISO timestamp), and rated_before_viewing_llm_scores=yes only if true. Keep private_mapping.json away from raters. Do not fabricate ratings or ask an LLM to fill them as human judgments.

If fewer than ten non-null successful full-system messages exist, this command correctly stops. Expand the predeclared cohort and run it consistently across configurations; do not select cases by desired outcomes or count silence as a message. Keep final evaluation files/cohort consistent rather than mixing old prompt versions.

## 10. LLM judge, human–LLM differences and plots

After human ratings are complete, score all nine runs with a separate judge invocation:

```bash
python3 -m coach evaluate-study --runs runs/study --score \
  --provider gemini --model gemini-3.5-flash-lite
```

This consumes API quota for each successful non-null message. The judge receives the recorded evaluation context and a fixed rubric. Judge settings/prompt and traces are saved in each run's judge/ directory. Keep judge provider/model/rubric fixed across comparisons. Failed cases are counted in execution success, not silently converted to judge scores.

Compute the required human–LLM mean absolute differences and disagreements:

```bash
python3 -m coach report \
  --outputs runs/study/full_rep1/outputs.jsonl \
  --judge runs/study/full_rep1/judge/judge_scores.jsonl \
  --human evaluations/human_full/ratings.csv \
  --mapping evaluations/human_full/private_mapping.json \
  --out runs/study/full_rep1/report

python3 -m coach plots --runs runs/study --out runs/study/figures
```

The first evaluate-study writes comparison.csv and per-run reports. Run the human report AFTER it, then plots: rerunning evaluate-study would overwrite the full report without human metrics. If you regenerate aggregation, rerun the human report afterward. Never rerun --score over existing judge scores; inspect failures and use deliberate new evaluation paths/commands rather than overwriting work.

Metrics: execution success, decision appropriateness when annotated, judge quality, at least ten human ratings, per-dimension/overall human–LLM MAE and notable disagreements, latency/call/token means. Latency includes model steps, pacing/failover waits and tools, excluding offline context preparation and judge evaluation. Explain that preprocessing is offline. Total tokens are null when any attempt has unavailable usage, and missing-usage counts are reported. Figures use the generated reports, so missing annotations/ratings lead to missing metrics rather than invented bars.

## 11. Output fields and submission status

outputs.jsonl: one record per attempted case; case_id, participant_id, decision_time, config_id, provider/model, status/error, decision, final_message, evidence, trace, evaluation_context, acceptable_decisions. trace includes actual LLM calls, token completeness, latency, planning/reflection counts and review status. traces.jsonl contains model inputs/outputs, tools, review/grounding events, errors and credential variable names (never key values). manifest.json identifies configuration, input hashes and grounding-related implementation hashes. execution_summary.json lists failures.

Submit code/dependencies and commands, reproducible cases and simulated profiles/history, final JSONL outputs and traces, evaluated reports/figures, rubric/judge prompt, human-rating evidence, case-selection and model details, and the written report/presentation. Follow course dataset redistribution rules; do not submit secrets. The code implements the required patterns and comparison controls, but the project is NOT finished until live outputs demonstrate those patterns and the evaluations/report/presentation are completed. A connectivity success is not a result for the model-choice experiment.

## Local validation of this patch

58 automated tests passed, including rate-limit failover, cooldown cycling, shared-project skipping, invalid-key disabling, deduplication, secret redaction, legacy/manual compatibility, generated A/B configuration equivalence, simulated-history timing and the prior data/grounding tests. No live API credentials were available here, so run the connectivity check and the model-B architecture command on your machine. The two live-model runs and human ratings have NOT been performed by this patch.
