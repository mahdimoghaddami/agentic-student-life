# Pilot audit and grounding fix

Apply this patch after studentlife_expanded_architecture_patch.zip. Existing prepared contexts are compatible; there is no need to scan raw data again. Keep the original run unchanged as a pilot.

## Findings from the supplied pilot outputs and traces

- 16 successful cases, 5 suggest and 11 no_message.
- 48 model calls (plan, draft, review for each case), 261,807 total recorded tokens.
- All 16 model reviews accepted with empty issues; no revision calls occurred.
- No tool calls occurred. Context was supplied directly, so this does not demonstrate active tool use.
- Five evidence/message deadline claims incorrectly promoted a previous local day's Class response to "today": u00_2013-03-28, u01_2013-03-28, u02_2013-03-28, u02_2013-03-30 and u00_2013-04-01.
- Example: u02's response at 2013-03-28T00:00:52Z is March 27 at 20:00:52 in New York. It cannot establish a March 28 deadline. The earlier March 27 case's 04:07 UTC response WAS on the same local date; it was not a confirmed deadline error.
- Sleep answers establish reported duration/quality but not a verified sleep-episode date. "In your latest sleep report" is preferable to automatically saying "last night".
- Evidence IDs were not consistently resolvable. The old context did not provide canonical IDs for these features; this patch fixes that interface.

## What changes

coach/data/contexts.py transforms existing frozen context into a compact agent view. Exact original contexts remain unchanged on disk. Latest EMA values retain questionnaire meaning, age, local submission time and value, with deterministic ev_ IDs and sources. Class.due gets a local reference_date and applies_to_decision_day flag. Sleep gets an explicit retrospective/uncertain-night label. History retains category counts, counts and available baseline summaries, but omits the repeated last-four-response lists. Sensor and history aggregates receive stable IDs. The duplicate top-level evidence list is removed.

Source IDs are stable for identical participant/feature/content inputs under this view version; they are not a universal raw-dataset ID convention. Aggregate IDs incorporate the decision time. Raw context remains available for audit.

The prompt requires exact observation IDs and source names. Supplied profiles/history and authored skills/resources retain their separate provenance. A deterministic validator checks references and a narrow pattern of stale deadline claims. It is not a general semantic verifier. It may miss paraphrases; human/judge evaluation remains required. Sleep wording is guided by temporal labels and reviewer instructions, not a complete natural-language rule engine.

Before each allowed review, grounding issues are passed to the reviewer. If that model accepts despite those issues, the effective review rejects and requests correction within the existing reflection budget. Traces store model_review separately from the effective review and deterministic_issues. This distinction must be reported: deterministic rejection is not credited as an LLM-discovered error. No-reflection runs still receive the same final validation, but no automatic repair call. Failed final validation is visible and the attempted draft is retained in a grounding_check trace event. No model switch, fallback answer, hidden retry, or new mandatory model stage is introduced.

Run manifests hash the grounding, context, orchestration and prompt implementation files. Apply this exact version consistently to all compared configurations; do not mix old pilot results with final revised results.

## Install and test

```bash
cd /mnt/c/CSI4900/studentlife_coach
python3 -m zipfile -c studentlife_before_grounding_fix.zip coach
python3 -m zipfile -e /path/to/studentlife_grounding_fix.zip .
python3 -m unittest discover -s tests -v
```

This replaces coach/data/contexts.py, coach/orchestrator.py, coach/prompts.py and coach/runner.py; adds coach/data/grounding.py, regression tests and this README. Back up any local edits first.

## Four-case paid pilot, without preparing data again

The selected cases include a supported same-day deadline and three cases with confirmed stale-deadline claims. This is a targeted regression pilot, not a representative evaluation cohort.

```bash
python3 - <<'PY'
import json
from pathlib import Path
wanted={'u00_2013-03-27','u00_2013-03-28','u02_2013-03-28','u00_2013-04-01'}
for name in ('cases','contexts'):
    rows=[json.loads(line) for line in Path(f'data/{name}.real.jsonl').read_text().splitlines() if line.strip()]
    selected=[r for r in rows if r['case_id'] in wanted]
    assert {r['case_id'] for r in selected}==wanted, f'Missing selected {name}'
    target=Path(f'data/{name}.grounding_pilot.jsonl')
    with target.open('x',encoding='utf-8') as f:
        for row in selected:f.write(json.dumps(row,ensure_ascii=False)+'\n')
    print('Wrote',target)
PY

python3 -m coach run \
  --config configs/full.json \
  --cases data/cases.grounding_pilot.jsonl \
  --contexts data/contexts.grounding_pilot.jsonl \
  --out runs/grounding_pilot_01
```

Selection itself uses no API calls. The coach run consumes model quota. Keep the same .env; no credential change is required. Inspect messages, evidence and review events before scaling. Failures can be legitimate validator catches and should not be silently filtered from evaluation.

Once the pilot is satisfactory, run all 16 original cases with the new code and a fresh output directory, then perform all nine ablations using the same original cases/context files. Larger, more varied cohorts and nonempty simulated interaction histories are still needed to evaluate generalization, personalization and adaptation. The successful pipeline alone does not complete the coursework evaluation.

## Validation and efficiency

48 tests passed, including New York date conversion across midnight/DST, exact ID/source checks, clarification questions, unchanged reflection budgets and final validation in no-reflection runs. The five known stale deadline claims are detected when replayed through the validator (without cloud calls). Serialized expanded-context characters fell from 173,807 to 111,536 across the 16 supplied cases: 35.8%. This is a character reduction, not a measured token or price reduction. Prompts now include stricter instructions; actual token savings and response improvements require a fresh live run. No new cloud calls were made during development.
