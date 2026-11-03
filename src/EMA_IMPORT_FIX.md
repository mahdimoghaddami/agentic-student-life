# StudentLife EMA import fix

Apply from the existing project root. This patch replaces coach/data/importer.py and coach/data/features.py; back up those files if you have made local edits. It adds a reviewed mapping and regression tests. It does not change model configuration or credentials. Raw dataset files are read only.

```bash
cd /mnt/c/CSI4900/studentlife_coach
python3 -m zipfile -e /path/to/studentlife_ema_import_fix.zip .
python3 -m unittest discover -s tests -v
python3 -m coach import-data --root dataset --mapping configs/import_mapping.studentlife.json --out data/observations.jsonl
```

The mapping checks the supplied original definition SHA256: cabde0ae9a66a07c719a29c10dc74917babefd35ad4168c715b1787e54297083.

Sleep hour codes: 1 means <3 hours (preserved as text, excluded from numerical medians); codes 2 through 19 mean 3.5 through 12 hours in 0.5-hour steps. In particular code 8 means 6.5 hours, 9 means 7 hours, and 11 means 8 hours. Sleep quality and daytime sleepiness are preserved under attributes. Sleep.social is daytime sleepiness, not social interaction.

Stress: 1 A little stressed; 2 Definitely stressed; 3 Stressed out; 4 Feeling good; 5 Feeling great. Values are labels, not ordinal numerical scores.

Missing named answers are skipped only for streams explicitly configured with skip_missing_answer. Their file, zero-based row, field and reason are recorded in data/observations.jsonl.audit.json. Unnamed answers are never guessed from values, coordinates or nearby timestamps. Unknown nonempty codes still fail the entire import and appear in .errors.json. Failed imports do not replace an existing observations file; do not use an old output as evidence of a successful new import.

Based on the supplied audit, expect 254 sleep records and 241 stress records without the required named answer; actual exclusions are reported by your run. Valid values and timestamps still need to pass validation. The full archive was not available here.

Summaries retain only the last four observations per stream in model context, with observations_truncated flag and full count. Window aggregates still use all available records; numerical sleep baseline excludes the latest observation and nonnumeric categories. This caps summary payload size but does not make whole-dataset import streaming or prevent full-record retrieval by other tools.

This patch supports the original four streams (sleep, stress, activity, conversation). It coexists with studentlife_context but does not connect that separate package to the coaching runner or claim that all dataset directories are used. Activity codes remain raw categories; sample proportions are not durations. Location coordinates are not copied into observations.

Importing real observations alone does not change default demo cases. Build participant-matched cases and pass both --cases and --observations to coach run. Use `python3 -m coach build-cases --help` for your existing case/profile interface. Do not run the demo cases against real observations and interpret missing matches as real evidence.

Validation: 31 unit tests passed, using synthetic data and mocked/local model endpoints, without cloud API calls.
