# Corrected experiments

- `2026-11-04_v1`: interrupted before schedule and retry fixes; archived, excluded from final results.
- `2026-11-04_v2`: interrupted by the free-tier daily quota; archived, excluded from final results.
- `2026-11-04_v3`: completed suite: nine configurations, 180 valid final outputs, 140 non-null messages independently judged, and 10 human ratings completed before judging.

The full-system v3 outputs and human ratings were reused. Eight additional required variants were generated. Planning-three had one HTTP 504 failure; only the failed case and a later dependent same-student case were replayed. Its initial outputs, failure record, and recovery accounting remain available. Total case attempts: 182. All 127 original files in `runs/` remain unchanged.

Read [the corrected report](2026-11-04_v3/report/corrected_report.pdf), [comparison CSV](2026-11-04_v3/comparison.csv), [detailed metrics](2026-11-04_v3/summary_metrics.json), and [execution/cost summary](2026-11-04_v3/execution_summary.json). Raw preference proxy flags are preserved alongside a qualitative review of three false positives.

Successful-response token estimates for v3, including preflight: Google $3.480825 and OpenAI $0.401094. Google uncertain failures carry an additional conservative reservation of $9.439819; this is not confirmed billed spend. Earlier attempts have separate ledgers. No process remains running after completion.

The human rating HTML/CSV and completed JSON are under `2026-11-04_v3/full/human_eval/`. Do not regenerate the rating sheet over completed ratings for different messages. Commands for resuming and offline reproduction are in the repository README.
