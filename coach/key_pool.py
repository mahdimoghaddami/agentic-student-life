"""Bounded sticky failover through Gemini credentials, with cooldowns.

State is shared across model objects within one sequential process. It is not a
cross-process scheduler. No model substitution occurs.
"""
import os,time,sys
from .credentials import gemini_pool
_CURSOR={}
_DISABLED={}

def ask_with_pool(client,stage,system,payload):
    from .models import _BLOCKED
    pool=gemini_pool();model_key=(client.provider,client.model)
    signature=tuple(p[2] for p in pool);cursor_key=(model_key,signature)
    cursor=_CURSOR.get(cursor_key,0)
    retries=max(0,min(8,int(os.getenv('GEMINI_MAX_RETRIES','3'))))
    max_wait=max(0.,float(os.getenv('GEMINI_MAX_RETRY_WAIT_SECONDS','120')))
    max_attempts=len(pool)*(retries+1);attempts=0;waited=0.;last_error=None
    while attempts<max_attempts:
        chosen=None;cooldowns=[]
        now=time.monotonic()
        for offset in range(len(pool)):
            index=(cursor+offset)%len(pool)
            name,secret,fingerprint,group=pool[index]
            if fingerprint in _DISABLED:continue
            scope=(*model_key,group)
            block=_BLOCKED.get(scope)
            if block and block[0]>now:
                cooldowns.append(block[0]-now);continue
            chosen=(index,name,secret,fingerprint,scope);break
        if chosen is None:
            delay=min(cooldowns,default=float('inf'))
            if delay==float('inf') or waited+delay>max_wait:
                raise RuntimeError('All configured Gemini keys are unavailable for this model; no fallback model used. '+(last_error or 'Keys are disabled or cooling down.'))
            print(f'All Gemini keys cooling down; waiting {delay:.1f}s.',file=sys.stderr,flush=True)
            time.sleep(delay);waited+=delay
            # Clock is rechecked on every selection; Retry-After is never shortened.
            continue
        index,name,secret,fingerprint,scope=chosen
        client._pool_credential=(name,secret);client._pool_scope=scope
        attempts+=1
        before=len(client.calls)
        try:
            result=client._ask_selected(stage,system,payload)
            client.calls[-1]['pool_attempt']=attempts
            _CURSOR[cursor_key]=index
            return result
        except RuntimeError as exc:
            rec=client.calls[-1] if len(client.calls)>before else {}
            diagnostic=rec.get('provider_error',{});status=diagnostic.get('http_status')
            if status not in (401,403,429,500,502,503,504):raise
            last_error=str(exc)
            rec['pool_attempt']=attempts;rec['key_failover']=True
            if status in (401,403):_DISABLED[fingerprint]=last_error
            elif status!=429:
                delay=max(1.,float(os.getenv('GEMINI_RETRY_BASE_SECONDS','15')),diagnostic.get('retry_after_s') or 0)
                _BLOCKED[scope]=(time.monotonic()+delay,last_error)
            cursor=(index+1)%len(pool);_CURSOR[cursor_key]=cursor
            print(f'{name}: HTTP {status}; selecting the next eligible key.',file=sys.stderr,flush=True)
        finally:
            client._pool_credential=None;client._pool_scope=None
    raise RuntimeError(f'Gemini key-pool attempt budget exhausted ({max_attempts} requests). '+(last_error or 'No successful request.'))
