"""Small live connectivity check for the two frozen study models (uses API quota)."""
import argparse,sys,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from coach.config import load_config,resolve_model
from coach.io import load_env,write_json
from coach.models import Model,_redact

def main():
    p=argparse.ArgumentParser();p.add_argument('--configs',default='configs/study');p.add_argument('--out',default='runs/model_check.json');a=p.parse_args();load_env()
    configs=[load_config(Path(a.configs)/(name+'.json')) for name in ('full','model_b')]
    identities=[resolve_model(c.provider,c.model) for c in configs]
    if identities[0]==identities[1]:raise ValueError('Model A and B must differ')
    if Path(a.out).exists():raise ValueError('Output exists; use a fresh --out')
    results=[]
    for cfg in configs:
        client=Model(cfg.provider,cfg.model,temperature=0,max_tokens=cfg.max_tokens)
        r={'config':cfg.name,'provider':client.provider,'model':client.model}
        try:
            answer=client.ask('connectivity','Return a JSON object with ok set to true.',{'check':'connectivity'})
            if answer.get('ok') is not True:raise ValueError('Connectivity response did not contain ok=true')
            r['status']='ok'
        except Exception as exc:r.update(status='failed',error=_redact(exc))
        r['calls']=client.calls;results.append(r)
        print(cfg.name,r['status'],client.provider,client.model)
    write_json(a.out,results)
    if any(r['status']!='ok' for r in results):raise SystemExit(1)
if __name__=='__main__':main()
