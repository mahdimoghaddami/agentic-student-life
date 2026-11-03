import csv
from pathlib import Path
from .judge import judge
from .metrics import report

def evaluate_study(root,provider,model,score=False,allow_mock=False):
    rows=[]
    for outputs in sorted(Path(root).glob('*/outputs.jsonl')):
        folder=outputs.parent; scores=folder/'judge/judge_scores.jsonl'
        if score:
            if scores.exists(): raise ValueError(f'Judge scores already exist: {scores}; omit --score to aggregate')
            judge(outputs,folder/'judge',provider,model,allow_mock)
        result=report(outputs,folder/'report',scores if scores.exists() else None)
        flat={'run':folder.name}
        for key in ('cases','is_mock','success_rate','decision_appropriateness','decision_annotation_count','mean_latency_s','mean_llm_calls','mean_tokens','missing_token_usage_cases','judge_n','judge_failed'):
            flat[key]=result.get(key)
        for key,value in result.get('judge_means',{}).items():flat['judge_'+key]=value
        rows.append(flat)
    if not rows:raise ValueError('No run outputs found')
    fields=list(dict.fromkeys(k for r in rows for k in r))
    with (Path(root)/'comparison.csv').open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)
    return rows
