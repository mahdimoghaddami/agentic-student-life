"""Load frozen, case-matched evidence; keep preparation diagnostics out of prompts."""
from copy import deepcopy
from ..io import read_jsonl,epoch

def agent_context(row):
    result=deepcopy({k:row[k] for k in ('observations','evidence','missing_or_unavailable','provenance')})
    # Counts of future rows reveal future participation even if values are hidden.
    def clean(value):
        if isinstance(value,dict):
            return {k:clean(v) for k,v in value.items() if k not in
                    ('quality','excluded_future_rows','invalid_rows','after_cutoff')}
        if isinstance(value,list):return [clean(v) for v in value]
        return value
    result=clean(result)
    from .grounding import compact_context
    return compact_context(result,row)

def load_contexts(path,cases):
    rows=read_jsonl(path); by_id={}
    for row in rows:
        key=row.get('case_id')
        if not key or key in by_id:raise ValueError('Missing or duplicate context case_id')
        by_id[key]=row
    expected={c['case_id'] for c in cases}
    if set(by_id)!=expected:raise ValueError('Contexts must match the exact case ID set; prepare using the same --cases file')
    result={}
    for case in cases:
        row=by_id[case['case_id']]
        if row.get('status')!='ok':raise ValueError('Context preparation failed for '+case['case_id'])
        cutoff=epoch(case['decision_time'])
        if row.get('participant_id')!=case['participant_id'] or epoch(row['decision_time'])!=cutoff:
            raise ValueError('Context participant or decision time mismatch: '+case['case_id'])
        for k in ('observations','evidence','missing_or_unavailable','provenance'):
            if k not in row:raise ValueError('Context missing '+k)
        if not any(row['observations'].get('ema',{}).get('latest',{})) and not any(
                not s.get('missing',True) for s in row['observations'].get('sensing',{}).values()):
            raise ValueError('No usable EMA or sensing for '+case['case_id']+'; verify participant and dates')
        def check(value):
            if isinstance(value,dict):
                for k,v in value.items():
                    if k in ('observed_at','available_at','end_at','last_observation') and v is not None and epoch(v)>cutoff:
                        raise ValueError('Future evidence in context: '+case['case_id'])
                    check(v)
            elif isinstance(value,list):
                for v in value:check(v)
        check(row['observations']);check(row['evidence'])
        result[case['case_id']]=agent_context(row)
    return result
