# StudentLife Multi-Agent Coach

A modular research simulation for the CSI 4900/5900 project. Python 3.10+.
Three roles: Planner → Coach → Reviewer, with bounded tool use, planning,
reflection, SQLite memory, coaching skills, model comparisons, and blinded ratings.
No transformer or other predictive model is trained. Numerical historical features
provide the factual foundation. Raw records and personal information stay out of git.

**Status:** implementation and offline fixtures are included. No real StudentLife
archive or API credentials were supplied. Bundled observations are synthetic. Mock
outputs and mock judge scores test software only and are NOT research results.
Real-data import and live model runs must be completed locally. Human ratings must
be completed by a person. Report and presentation outlines contain no invented results.

## 1. Install and run the offline demo

Unzip, open a terminal in this directory, then:

```bash
python3 -m venv .venv
# Windows PowerShell:
.venv\Scripts\Activate.ps1
# Linux / WSL instead:
# source .venv/bin/activate
python3 -m pip install -e ".[plots]"
python3 -m unittest discover -s tests -v
python3 -m coach run --config configs/mock.json --out runs/demo
python3 -m coach run --config configs/mock.json --cases examples/episodes.jsonl --episodes --out runs/demo_episode
python3 -m coach report --outputs runs/demo/outputs.jsonl --out runs/demo/report
```

Use a new output directory for every run. Existing nonempty directories are refused
to prevent accidental overwrite or memory contamination. Remove only a run directory
you intend to discard to reset it; starting in a new directory is the preferred reset.
Windows needs tzdata, installed through the package dependency.

## 2. Choose your models

Copy `.env.example` to `.env`. Set `COACH_PROVIDER=ollama` and `OLLAMA_MODEL` to an
installed model, or `COACH_PROVIDER=gemini` with `GEMINI_API_KEY` and `GEMINI_MODEL`.
The Gemini adapter accepts `openai:MODEL_NAME` and strips the prefix. For example,
your requested `openai:gemini-3.5-flash-lite` can be entered if that exact model is
available to your account; this project does not assume its availability. Ollama
must already be running and have your selected model downloaded.

Set `MODEL_B_PROVIDER`, `MODEL_B`, `JUDGE_PROVIDER`, and `JUDGE_MODEL` separately.
Use two genuinely different models for the model-choice comparison. The judge is
an independent client and prompt, outside the coach and its timing. Prefer a judge
model different from the evaluated models. Keep the judge fixed across comparisons.

```bash
python3 -m coach run --config configs/full.json --out runs/live_fixture
```

This runs a real LLM on **synthetic cases**. It checks your connection before using
real data. Structured JSON tool requests are interpreted by the bounded executor;
provider-specific native function-calling support is not required. Requests are real
Python function calls, and their arguments/results are logged. Unknown tools are
rejected and returned as errors. Network/JSON failures are recorded as failed cases;
there are no hidden retries, heuristic substitutions, or fabricated token counts.
Missing provider token usage is null and explicitly counted in reports.

## 3. Import StudentLife

Download the archive yourself from the course dataset link, extract it, and find the
root containing `sensing/` and `EMA/`. Raw data are never modified.

```bash
python3 -m coach inspect --root /path/to/dataset --out dataset_inspection.json
```

Read the inspection file, including the actual EMA definition. Copy
`configs/import_mapping.template.json` to `configs/import_mapping.local.json`.
Update field names and all questionnaire code mappings using your local definition;
paste its SHA256 from the inspection into `ema_definition_sha256`.

**The template is intentionally incomplete:** it contains only the two stress-code
examples and one sleep-code example supplied by the course guide. It cannot safely
decode every record until you complete it. Unknown codes fail loudly rather than
silently treating them as ordinal scores. For JSON wrappers set `records_key` in
the stream specification. Set `missing_codes` only to codes documented as missing.
Use numeric hours in the sleep `values` mapping; use decoded strings for stress.
CSV column whitespace is stripped. Activity category labels can be mapped using
`values`; otherwise raw category codes are retained and are not interpreted as time.

```bash
python -m coach import-data --root /path/to/dataset --mapping configs/import_mapping.local.json --out data/observations.jsonl
```

Import is all-or-nothing. Errors are written to `data/observations.jsonl.errors.json`.
Every record has observation and availability timestamps. For EMA the response
submission time controls availability, even if describing the previous night.
Completed conversation intervals are withheld until their end. Duplicate records
are removed; overlapping conversation intervals are merged during summarization.
Summaries use trailing elapsed-time windows (7×24 hours by default), not calendar
midnights. Case decision times use America/New_York, including daylight saving time.
Sleep baseline is the median of earlier available sleep observations in the window,
excluding the latest observation; it is not a population norm. No coverage is assumed.

## 4. Build and curate evaluation cases

Create profiles keyed by actual participant IDs using `examples/profiles.template.json`.
Keep `source: simulated_profile`; these goals/preferences do not come from StudentLife.

```bash
python -m coach build-cases --observations data/observations.jsonl --profiles data/profiles.json --limit 100 --out data/cases.jsonl
```

This selects observed participant-days at 09:00 the following local day, sorted by
decision time then participant, capped by limit. It does not select for high stress.
Document any subsequent selection changes. Check participant representation and
coverage before freezing the case list. Use a separate development case list for
prompt changes; freeze the evaluation list before comparing configurations.

Each case requires `case_id`, `participant_id`, `decision_time`, `profile`, and
`history`. Optional fields: `episode_id`, `case_kind`, `acceptable_decisions`.
History events require `id`, `at`, `kind`, `source`. Preference updates add an
`updates` dictionary; feedback may include `value: rejected` and `detail`.
Explicit updates are ordered by time and override prior profile fields. They are
never inferred from sensing. Future events are excluded. Base profile fields must
be known at case start; later changes belong in history.

Add reproducible missing-data and preference-update cases. If intentionally masking
real observations, save a separate derived observation file and label the alteration
as simulated; never misrepresent it as actual sensor absence. The included 16 cases
and 3-step episode illustrate the schema. For real curated cases, annotate the
acceptable decisions *before* model evaluation. Naturalistic cases may leave this
list empty; they are excluded from decision-appropriateness accuracy and the count
is reported. These annotations are researcher judgments, not dataset ground truth.

Fixed-context runs isolate memory per case. `--episodes` shares memory only within an
episode and participant, sorted chronologically, and accumulates generated messages.
For comparable fixed-context ablations use the same input files. Episode comparisons
are separate because generated histories naturally diverge. Scripted feedback is
exogenous simulated input, not a claim that a participant responded to generated advice.

## 5. Run all required ablations

```bash
python -m coach ablations --cases data/cases.jsonl --observations data/observations.jsonl --config configs/full.json --out runs/study --repeats 1
```

Nine configurations: full, single, no_reflection, no_planning, reflection_2,
reflection_3, planning_2, planning_3, model_b. The reference supplies depth 1.
All start from isolated memory and identical supplied cases and tools. Single-agent
uses one unified system prompt and shared working history with self-planning and self-review; multi-agent uses distinct role
prompts and explicit exchanges. Removing planning leaves Coach + Reviewer; removing
reflection leaves Planner + Coach. Final multi-agent configurations retain >=2 agents.
Optional memory/tools/skills ablations can be made by copying a config and toggling
its boolean fields. Their effects should be described separately from required runs.

One planning round produces or updates a structured plan after bounded tool retrieval.
`ready=true` stops planning early. One reflection cycle reviews a draft and, if needed,
revises it. Acceptance stops early. At exhausted reflection budget the last valid
revision is emitted, even if it has not had another review; logs expose that fact.
Depth is a maximum, not a promise of extra calls. Record actual depths alongside
maximum budgets. `tool_turns` bounds tool batches per stage, at most six calls per
batch. Model requests use temperature 0 by default; this is not a guarantee of exact
repeatability. For stronger comparisons use `--repeats 3`; retain per-repeat results.

## 6. Human and independent LLM evaluation

Export human forms from the chosen **final configuration**, before revealing scores:

```bash
python -m coach human-export --outputs runs/study/full_rep1/outputs.jsonl --out ratings/final --n 10
```

Give the rater only `ratings.csv` and `RUBRIC.txt`. It includes the same context used
by the judge, including available tool results. Keep `private_mapping.json` private.
The person fills all three 1–5 scores, notes, timestamp, and the independence
attestation. Do not invent human ratings. At least 10 non-null successful messages
must be available; run more cases if necessary. Selection is seeded and shuffled.

```bash
python -m coach judge --outputs runs/study/full_rep1/outputs.jsonl --out runs/study/full_rep1/judge
python -m coach report --outputs runs/study/full_rep1/outputs.jsonl --judge runs/study/full_rep1/judge/judge_scores.jsonl --human ratings/final/ratings.csv --mapping ratings/final/private_mapping.json --out runs/study/full_rep1/report
```

To score all ablations and generate a comparison CSV in one command:

```bash
python -m coach evaluate-study --runs runs/study --score
```

Without `--score`, this aggregates existing scores without new API calls. Existing judge
files are protected from overwrite in this batch command. Add human ratings to the
final-system report separately **after** batch aggregation, which regenerates reports.

Alternatively, run the judge and regenerate the report for **each ablation**, omitting human options
for configurations without human ratings. The judge scores every successful non-null
message. Null messages do not receive fabricated quality scores. The rubric, judge
settings, complete inputs, outputs, and failures are saved. Use the same judge model
and settings throughout. Inspect disagreement records before writing the discussion.

For testing the evaluation plumbing only:

```bash
python -m coach judge --outputs runs/demo/outputs.jsonl --out runs/demo/judge --provider mock --model mock --allow-mock
python -m coach report --outputs runs/demo/outputs.jsonl --judge runs/demo/judge/judge_scores.jsonl --out runs/demo/report
```

Mock scores are constant fixtures, loudly marked, and unsuitable for the report.
Human–LLM MAE is averaged over matched ratings, per dimension and overall. Judge means
use all successfully judged messages; human comparisons use only the rated subset.
Report denominators and judge failures. Different message rates can affect quality
averages, so inspect decision rates and appropriateness alongside message quality.

## 7. Figures, report, presentation

```bash
python -m coach plots --runs runs/study --out runs/study/figures
```

Generates efficiency, success, decision appropriateness, and (when scored) quality
and agreement figures. Each run also has JSON metrics and a Markdown table. The
`docs/report_outline.md`, `docs/presentation_outline.md`, and `docs/requirements.md`
cover the final deliverables. Fill them with actual results; do not claim clinical
benefit or effectiveness from message-quality ratings.

## Output fields and logs

Each configuration writes `outputs.jsonl`, exactly one record per attempted case:

| Field | Meaning |
|---|---|
| case_id / participant_id / decision_time | Stable identity and available-information cutoff |
| config_id / provider / model / is_mock | Experiment and model provenance |
| status / error | ok or failed; failures are never counted as silence |
| decision | suggest, clarify, no_message; null on failure |
| evidence | Source labels, optional IDs, concise supporting details |
| final_message | Text or null |
| trace.llm_calls | All attempted coaching model calls, including failed calls |
| trace.total_tokens | Provider totals summed across calls, or null if incomplete |
| trace.latency_s | End-to-end case time, including context, tools, models, validation, and memory write; excludes offline ingestion, judge, and output-file serialization |
| trace.planning_rounds / reflection_cycles | Actual budgets consumed |
| evaluation_context | Available observations, profile/history, and retrieved tool evidence for audit/judging |
| acceptable_decisions | Optional researcher annotations, never supplied to coach agents |

`traces.jsonl` stores structured plans, reviews, tool calls, role prompts and model
responses (not private chain-of-thought). `manifest.json` records settings, input
SHA256s, Python/platform, and case mode. `execution_summary.json` lists failures.
Logs contain student data: treat them as sensitive. API keys are never written.

## Source layout

`coach/data/`: inspection, import, summaries, case construction.
`coach/agents/`: separate Planner, Coach, Reviewer, shared bounded executor.
`coach/models.py`: Ollama/Gemini adapters. `coach/mock.py`: offline fixtures.
`coach/tools.py`: tools and authored coaching skills. `coach/memory.py`: SQLite store.
`coach/orchestrator.py`: one case. `coach/runner.py`: dataset execution.
`coach/ablations.py`: required experiment matrix. `coach/evaluation/`: judge, blinded
forms, metrics, plots. `tests/`: temporal, memory, budget, import, API-contract tests.

## References and limitations

Course assignment and supplied StudentLife Quick Start guide govern the submission.
Dataset: https://www.kaggle.com/datasets/dartweichen/student-life
Study: https://studentlife.cs.dartmouth.edu/
Gemini compatibility: https://ai.google.dev/gemini-api/docs/openai
Ollama API: https://github.com/ollama/ollama/blob/main/docs/api.md

The adapters follow these documented request shapes; model availability and provider
features vary. No external model was reachable with user credentials during delivery.
The importer is configurable because your actual archive was not supplied. It requires
schema/codebook verification. No stress forecasting or causal intervention model is
trained. The catalog is explicitly simulated, with no fabricated campus contacts.
The coach is a coursework simulation of everyday support, not a clinical assessment.
Remember to sign up on the course group sheet, including when working individually.
