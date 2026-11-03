import os
from pathlib import Path
from dataclasses import replace
from .config import Config
from .runner import run
from .evaluation.metrics import report
from .io import write_json

def configurations(base,model_b_provider,model_b):
    return [replace(base,name='full'),replace(base,name='single',mode='single'),replace(base,name='no_reflection',reflection_cycles=0),replace(base,name='no_planning',planning_rounds=0),replace(base,name='reflection_2',reflection_cycles=2),replace(base,name='reflection_3',reflection_cycles=3),replace(base,name='planning_2',planning_rounds=2),replace(base,name='planning_3',planning_rounds=3),replace(base,name='model_b',provider=model_b_provider,model=model_b)]

def run_ablations(cases,observations,base,out,model_b_provider,model_b,repeats=1,contexts_path=None):
    from .config import resolve_model
    a=resolve_model(base.provider,base.model);b=resolve_model(model_b_provider,model_b)
    if a==b and a[0]!='mock': raise ValueError('Model B must differ from model A')
    if repeats<1: raise ValueError('repeats must be positive')
    configs=configurations(base,model_b_provider,model_b); summaries=[]
    for repeat in range(repeats):
        for cfg in configs:
            folder=Path(out)/(cfg.name+f'_rep{repeat+1}')
            summaries.append(run(cases,observations,cfg,folder,contexts_path=contexts_path))
            report(folder/'outputs.jsonl',folder/'report')
    write_json(Path(out)/'ablation_summary.json',{'repeats':repeats,'runs':summaries,'mock_only':a[0]=='mock','note':'Run separate judge evaluation and regenerate reports to compare message quality.'})
