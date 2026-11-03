# HTTP 429 patch

Extract this ZIP into the existing studentlife_coach project directory, replacing
coach/models.py. It does not contain or modify your .env or existing run outputs.
Optionally back up coach/models.py first. No dependency installation is needed.

The error body was previously discarded. This update displays Google's error message
and quota identifiers (with the configured API key redacted), adds Gemini request
pacing across case instances within a process, and bounded retries for transient
429/500/502/503/504 responses. It honors Retry-After and RetryInfo delays, declining
an automatic retry when the requested wait exceeds the configured maximum.
Explicit daily/zero/spend/billing quota errors are not retried. Exhausted 429 retries
pause subsequent same-model requests for at least 60 seconds; explicit hard quota
errors pause that model until the process exits. Cases remain recorded as failures.
Run one experiment process at a time: pacing is not coordinated across processes.

Defaults (optional additions to .env):

```dotenv
GEMINI_MIN_INTERVAL_SECONDS=6
GEMINI_MAX_RETRIES=3
GEMINI_RETRY_BASE_SECONDS=15
GEMINI_MAX_RETRY_WAIT_SECONDS=120
```

Six seconds spaces request starts to at most approximately 10/minute in this process.
It is a starting setting, not a guarantee of staying within your account's token or
request limits. If your RPM limit is 5, use an interval above 12 seconds, e.g. 13.
Daily quota, spend limits, and insufficient balance need quota reset/account action;
slowing calls does not fix those. Check the project's active Google AI Studio limits.

Each case may call Planner, Coach, and Reviewer plus tools/revisions. Thus five
successful cases may already represent substantially more than five API requests.

## Retry failed fixed-context cases only

From the project directory:

```bash
python3 tools/select_failed_cases.py --original examples/cases.jsonl --outputs runs/live_fixture/outputs.jsonl --out runs/live_fixture/failed_cases.jsonl
python3 -m coach run --config configs/full.json --cases runs/live_fixture/failed_cases.jsonl --out runs/live_fixture_retry
```

The new directory must not already contain a run. Do not judge this retry subset as
the complete evaluation: retain both original and retry records, and document the
retry policy. For final controlled ablations, use this same patched client/pacing
for all configurations and run the frozen case list afresh after quota is stable.
Do not use subset retries for sequential episodes, where prior outputs affect memory.

Retries count as additional model calls. Failed HTTP attempts have unknown token
usage, so existing totals become null if any attempt lacks usage. Case latency
includes pacing and retry waits. Report that these are operational latency measures.
The patch does not silently switch models or fabricate successful outputs.

## Verification

20 tests passed, including six new tests covering retry accounting, quota circuit
breaking, Retry-After, excessive requested delay, secret redaction, and pacing across
instances. No paid API requests were made during patch validation.

```bash
python3 -m unittest discover -s tests -v
```
