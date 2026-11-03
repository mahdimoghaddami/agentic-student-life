"""Freeze resolved model settings into individually runnable ablation configs."""
import argparse,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from dataclasses import replace
import os
from coach.io import load_env,write_json
from coach.config import load_config,resolve_model
from coach.ablations import configurations

def main():
    p=argparse.ArgumentParser();p.add_argument('--base',default='configs/full.json');p.add_argument('--out',default='configs/study');a=p.parse_args();load_env()
    base=load_config(a.base);provider,model=resolve_model(base.provider,base.model)
    bp,bm=resolve_model(os.getenv('MODEL_B_PROVIDER','gemini'),os.getenv('MODEL_B',''))
    if (provider,model)==(bp,bm):raise ValueError('MODEL_B must be a different model, not a second key for the same model')
    base=replace(base,name='full',provider=provider,model=model,mode='multi',planning_rounds=1,reflection_cycles=1)
    out=Path(a.out)
    if out.exists() and any(out.iterdir()):raise ValueError('Config directory must be empty; choose a new directory')
    cfgs=configurations(base,bp,bm)
    cfgs += [replace(base,name='no_tools',tools=False),replace(base,name='no_memory',memory=False),replace(base,name='no_skills',skills=False)]
    for cfg in cfgs:write_json(out/(cfg.name+'.json'),cfg.to_dict())
    print(f'Wrote {len(cfgs)} configs. A: {provider}/{model}; B: {bp}/{bm}. No API requests made.')
if __name__=='__main__':main()
