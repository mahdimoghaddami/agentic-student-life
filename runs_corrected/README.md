# Corrected experiment attempts

- `2026-11-04_v1`: interrupted; schedule and provider-retry issues subsequently fixed. Not a final experiment.
- `2026-11-04_v2`: interrupted by both credentials reaching the daily free-tier quota. Not a final experiment.
- `2026-11-04_v3`: completed full configuration, 20 successful cases, zero failed cases. This is the current full-system result.

All attempts and the original `runs/` are preserved. No ablation or automated judge calls have been made for this experiment.

## Human evaluation

Open `2026-11-04_v3/full/human_eval/blind_rating_sheet.html` in a browser. Rate all 10 messages on context awareness, goal alignment, and clarity (1–5), then click **Save my 10 ratings as JSON**. Keep the downloaded `human_ratings.json`; the file initially in this folder is an unfilled template. Rate before viewing automated judge scores. The 10 messages follow the scenario-based priority declared in `protocol.json` before generation, skipping null messages.

## Execution and costs

The v3 model was Gemini 3.6 Flash for all agents. All five patterns were enabled. The 30 offline regression tests and five leakage checks passed. Saved outputs also passed completeness, model identity, decision/message consistency, iteration-budget, and memory-time checks. These checks establish execution validity; they do not replace message-quality evaluation.

The v3 successful-response token estimate, including preflight, is $0.410175. Fifteen server failures carry an additional conservative reservation upper bound of $0.819594; that amount is not a confirmed billed charge. Actual charges and promotional credit use must be checked in Google billing. Earlier attempts have separate usage ledgers. See `2026-11-04_v3/execution_summary.json` for execution details.
