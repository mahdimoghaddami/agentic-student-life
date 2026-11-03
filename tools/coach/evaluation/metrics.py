import csv,json,statistics
from pathlib import Path
from collections import Counter
from ..io import read_jsonl,read_json,write_json
from .rubric import DIMENSIONS

def mean(values): return statistics.mean(values) if values else None

def summarize_run(outputs,judge_path=None,human_path=None,mapping_path=None):
    rows=read_jsonl(outputs); good=[r for r in rows if r['status']=='ok']
    annotated=[r for r in good if r.get('acceptable_decisions')]
    result={'cases':len(rows),'success_rate':len(good)/len(rows) if rows else None,'is_mock':any(r.get('is_mock') for r in rows),'decision_counts':dict(Counter(r['decision'] for r in good)),
    'decision_annotation_count':len(annotated),'decision_appropriateness':mean([r['decision'] in r['acceptable_decisions'] for r in annotated]),'efficiency_population':'all attempted cases',
    'mean_latency_s':mean([r['trace']['latency_s'] for r in rows]),'mean_llm_calls':mean([r['trace']['llm_calls'] for r in rows]),
    'mean_tokens':mean([r['trace']['total_tokens'] for r in rows if r['trace']['total_tokens'] is not None]),'missing_token_usage_cases':sum(r['trace']['total_tokens'] is None for r in rows)}
    judges={}
    if judge_path:
        jrows=read_jsonl(judge_path)
        judges={(j['config_id'],j['case_id']):j for j in jrows if j['status']=='ok'}
        result['judge_failed']=sum(j['status']!='ok' for j in jrows)
        result['judge_n']=len(judges)
        result['is_mock']=result['is_mock'] or any(j.get('is_mock') for j in jrows)
        result['judge_means']={d:mean([j['scores'][d] for j in judges.values()]) for d in DIMENSIONS}
    if human_path:
        if not mapping_path or not judge_path: raise ValueError('Human comparison requires mapping and judge scores')
        mapping=read_json(mapping_path); differences={d:[] for d in DIMENSIONS}; human_values={d:[] for d in DIMENSIONS}; disagreements=[];seen=set()
        with open(human_path,encoding='utf-8',newline='') as f:
            for h in csv.DictReader(f):
                if h['blind_id'] in seen: raise ValueError('Duplicate human rating')
                seen.add(h['blind_id'])
                if h['rated_before_viewing_llm_scores'].strip().lower()!='yes' or not h['rated_at'].strip(): raise ValueError('Human independence attestation and date required')
                m=mapping[h['blind_id']]; j=judges.get((m['config_id'],m['case_id']))
                if j is None: raise ValueError('Missing matched judge score')
                diff={}
                for d in DIMENSIONS:
                    v=int(h[d])
                    if not 1<=v<=5: raise ValueError('Human scores must be 1..5')
                    diff[d]=abs(v-j['scores'][d]);differences[d].append(diff[d]);human_values[d].append(v)
                disagreements.append(dict(m,differences=diff,human_notes=h['notes'],judge_rationale=j.get('rationale','')))
        if len(seen)<10: raise ValueError('At least 10 completed independent ratings required')
        result['human_n']=len(seen);result['human_means']={d:mean(v) for d,v in human_values.items()}
        result['human_llm_mae']={d:mean(v) for d,v in differences.items()}
        result['human_llm_mae_overall']=mean([v for values in differences.values() for v in values])
        result['notable_disagreements']=sorted(disagreements,key=lambda x:max(x['differences'].values()),reverse=True)
    return result

def report(outputs,out,judge_path=None,human_path=None,mapping_path=None):
    result=summarize_run(outputs,judge_path,human_path,mapping_path);out=Path(out);out.mkdir(parents=True,exist_ok=True)
    write_json(out/'metrics.json',result)
    lines=['# Evaluation summary', '', '**MOCK / SYNTHETIC: not research results.**' if result['is_mock'] else 'Results from recorded model runs.', '', '| Metric | Value |','|---|---|']
    for k,v in result.items():
        if not isinstance(v,(dict,list)): lines.append(f'| {k} | {v} |')
    for section in ('judge_means','human_means','human_llm_mae','decision_counts'):
        if section in result:
            lines+=['',f'## {section}','','| Dimension | Value |','|---|---|']
            lines += [f'| {k} | {v} |' for k,v in result[section].items()]
    (out/'summary.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    return result
