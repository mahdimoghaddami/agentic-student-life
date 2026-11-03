# Multiple Gemini credentials

Extract this patch inside your existing studentlife_coach directory. It contains
coach/models.py and coach/credentials.py plus tests; it includes the previous
rate-limit fix. It does not replace .env or any results. No new dependencies.

Store any number of numbered credentials locally:

```dotenv
GEMINI_API_KEY_1=YOUR_FIRST_KEY
GEMINI_API_KEY_2=YOUR_SECOND_KEY
GEMINI_API_KEY_3=YOUR_THIRD_KEY
GEMINI_KEY_SLOT=1
GEMINI_MIN_INTERVAL_SECONDS=6
GEMINI_MAX_RETRIES=0
```

Keep your existing model/provider settings. Change GEMINI_KEY_SLOT to select the
key used by the run, including judge runs. Numbered slots may be any positive integer.
If GEMINI_KEY_SLOT is absent or blank, the old GEMINI_API_KEY is used. A selected
missing key is an error and does not silently fall back to another key.

A command-line environment override takes precedence over .env:

```bash
GEMINI_KEY_SLOT=2 python3 -m coach run --config configs/full.json --out runs/key2_demo
```

Use a new output directory. With no --cases override this reruns all synthetic demo
cases and uses quota; it does not resume a previous run. If the demo already worked,
proceed with real data preparation instead of repeatedly rerunning it.

Keys do not automatically rotate after errors. Quota errors remain visible. Google
applies limits per project, not API key: multiple keys belonging to the same project
share its quota. This patch is for choosing credentials, not increasing quotas.
Pacing remains shared by model within one process; it is not coordinated between
separate processes. Run only one process against a given limited project at a time.

Trace records include only the credential variable name (such as GEMINI_API_KEY_2),
never its value. Error sanitization redacts every configured key. Never upload .env.

Validation: all 26 tests passed, including key selection, missing-key errors,
backwards compatibility, HTTP authorization selection, and multi-key redaction.
No live or paid API calls were made during verification.
