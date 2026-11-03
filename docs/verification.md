# Verification at delivery

- 14 automated tests passed (temporal leakage, interval merging, preference updates,
  episode memory, failure output, stage budgets, importer decoding, HTTP adapter
  request/response contracts, human export, and MAE calculation).
- Editable installation succeeded without fetching runtime dependencies on Linux.
- 16-case offline demo and 3-step episode completed.
- Nine mock experiment configurations × 16 cases = 144 successful case executions.
- 135 non-null mock messages passed through the judge/export/report pipeline.
- Comparison CSV and plots generated successfully.

These checks validate implementation plumbing, not LLM quality or model availability.
The mock judge returns fixture scores. No human ratings or research results have
been fabricated. Real archive ingestion, live API calls, Windows execution, and
independent human ratings remain to be verified on the user's machine.
