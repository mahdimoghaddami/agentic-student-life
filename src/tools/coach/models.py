"""Model adapters with bounded retries and per-process Gemini pacing."""
import json, os, time, re, sys, urllib.request, urllib.error
from email.utils import parsedate_to_datetime
from .config import resolve_model
from .mock import respond
from .credentials import gemini_credential, configured_secrets

_LAST_REQUEST = {}
_BLOCKED = {}

def _redact(text):
    text = str(text)
    for secret in sorted(set(configured_secrets()), key=len, reverse=True):
        text = text.replace(secret, '[REDACTED]')
    return re.sub(r'AIza[\w-]+', '[REDACTED]', text)

def _error_detail(exc):
    """Return provider diagnostics, never request headers or credentials."""
    try:
        raw = json.loads(exc.read(65536).decode('utf-8', errors='replace'))
        error = raw.get('error', raw)
        if not isinstance(error, dict):
            error = {'message': str(error)}
    except (ValueError, AttributeError):
        error = {'message': 'No structured error details supplied.'}
    message = _redact(error.get('message', ''))
    details = error.get('details', [])
    quotas, retry_after = [], None
    if isinstance(details, list):
        for detail in details:
            if not isinstance(detail, dict):
                continue
            for violation in detail.get('violations', []):
                if isinstance(violation, dict):
                    quotas.append({k: _redact(violation[k]) for k in ('quotaMetric', 'quotaId', 'quotaValue') if k in violation})
            delay = detail.get('retryDelay')
            if isinstance(delay, str) and delay.endswith('s'):
                try: retry_after = max(retry_after or 0, float(delay[:-1]))
                except ValueError: pass
    header = exc.headers.get('Retry-After') if exc.headers else None
    if header:
        try: seconds = float(header)
        except ValueError:
            try: seconds = parsedate_to_datetime(header).timestamp() - time.time()
            except (ValueError, TypeError, OverflowError): seconds = 0
        retry_after = max(retry_after or 0, seconds, 0)
    summary = {'http_status': exc.code, 'status': _redact(error.get('status', '')), 'message': message[:3000], 'quotas': quotas, 'retry_after_s': retry_after}
    marker = (message + ' ' + json.dumps(quotas)).lower()
    hard_quota = any(x in marker for x in ('perday', 'per_day', 'per day', 'daily', 'billing', 'spend limit', 'spend-based')) or bool(re.search(r'limit:\s*0\b', marker)) or any(q.get('quotaValue') == '0' for q in quotas)
    return summary, hard_quota

class Model:
    def __init__(self, provider, model, temperature=0, max_tokens=1200):
        self.provider, self.model = resolve_model(provider, model)
        self.temperature, self.max_tokens = temperature, max_tokens
        self.calls = []

    def ask(self, stage, system, payload):
        # Applies to Gemini only; mock tests and local inference are not paced.
        pacing = max(0., float(os.getenv('GEMINI_MIN_INTERVAL_SECONDS', '6')))
        retries = max(0, min(8, int(os.getenv('GEMINI_MAX_RETRIES', '3')))) if self.provider == 'gemini' else 0
        base_delay = max(0., float(os.getenv('GEMINI_RETRY_BASE_SECONDS', '15')))
        max_delay = max(0., float(os.getenv('GEMINI_MAX_RETRY_WAIT_SECONDS', '120')))
        key = (self.provider, self.model)
        blocked = _BLOCKED.get(key)
        if self.provider == 'gemini' and blocked and time.monotonic() < blocked[0]:
            raise RuntimeError('Gemini requests paused after quota/rate-limit failure; no new API request sent. ' + blocked[1])
        for attempt in range(retries + 1):
            if self.provider == 'gemini':
                wait = max(0., _LAST_REQUEST.get(key, -float('inf')) + pacing - time.monotonic())
                if wait: time.sleep(wait)
            rec = {'type':'model', 'stage':stage, 'provider':self.provider, 'model':self.model,
                   'temperature':self.temperature, 'max_tokens':self.max_tokens,
                   'system':system, 'input':payload, 'attempt':attempt + 1, 'total_tokens':None}
            self.calls.append(rec)
            start = time.perf_counter()
            try:
                if self.provider == 'mock':
                    result = respond(stage, payload)
                    rec['total_tokens'] = 0
                else:
                    messages = [{'role':'system','content':system}, {'role':'user','content':json.dumps(payload)}]
                    if self.provider == 'ollama':
                        url = os.getenv('OLLAMA_BASE_URL','http://localhost:11434').rstrip('/') + '/api/chat'
                        body = {'model':self.model,'messages':messages,'stream':False,'format':'json','options':{'temperature':self.temperature,'num_predict':self.max_tokens}}
                        headers = {'Content-Type':'application/json'}
                    else:
                        credential_name, api_key = gemini_credential()
                        rec['credential_name'] = credential_name
                        url = os.getenv('GEMINI_BASE_URL','https://generativelanguage.googleapis.com/v1beta/openai').rstrip('/') + '/chat/completions'
                        body = {'model':self.model,'messages':messages,'temperature':self.temperature,'max_tokens':self.max_tokens,'response_format':{'type':'json_object'}}
                        headers = {'Content-Type':'application/json','Authorization':'Bearer ' + api_key}
                    request = urllib.request.Request(url,data=json.dumps(body).encode(),headers=headers)
                    if self.provider == 'gemini': _LAST_REQUEST[key] = time.monotonic()
                    with urllib.request.urlopen(request,timeout=float(os.getenv('REQUEST_TIMEOUT','120'))) as response:
                        raw = json.load(response)
                    if self.provider == 'ollama':
                        content = raw['message']['content']
                        if 'prompt_eval_count' in raw and 'eval_count' in raw:
                            rec['total_tokens'] = raw['prompt_eval_count'] + raw['eval_count']
                    else:
                        content = raw['choices'][0]['message']['content']
                        rec['total_tokens'] = raw.get('usage',{}).get('total_tokens')
                    rec['raw_output'] = content
                    content = content.strip()
                    if content.startswith('```'): content = '\n'.join(content.splitlines()[1:-1])
                    result = json.loads(content)
                if not isinstance(result,dict): raise ValueError('Model output must be an object')
                rec['output'] = result
                return result
            except urllib.error.HTTPError as exc:
                diagnostic, hard_quota = _error_detail(exc)
                rec['provider_error'] = diagnostic
                reason = f"HTTP {exc.code} {diagnostic['status']}: {diagnostic['message']}"
                if diagnostic['quotas']: reason += ' Quota details: ' + json.dumps(diagnostic['quotas'])
                rec['error'] = reason
                delay = max(base_delay * 2**attempt, diagnostic['retry_after_s'] or 0)
                transient = self.provider == 'gemini' and exc.code in (429,500,502,503,504) and not hard_quota
                if transient and attempt < retries and delay <= max_delay:
                    rec['retry_wait_s'] = delay
                    print(f'Gemini HTTP {exc.code}; retry {attempt+1}/{retries} in {delay:.1f}s.', file=sys.stderr, flush=True)
                    time.sleep(delay)
                    continue
                if self.provider == 'gemini' and exc.code == 429:
                    cooldown = float('inf') if hard_quota else time.monotonic() + max(60., diagnostic['retry_after_s'] or 0)
                    _BLOCKED[key] = (cooldown, reason)
                raise RuntimeError(reason) from None
            except Exception as exc:
                rec['error'] = _redact(exc)
                raise
            finally:
                rec['latency_s'] = time.perf_counter() - start
