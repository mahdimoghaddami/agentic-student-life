import csv,random,json,hashlib
from pathlib import Path
from ..io import read_jsonl,write_json
from .rubric import DIMENSIONS,RUBRIC

def export_ratings(outputs,out,n=10,seed=42):
    rows=[r for r in read_jsonl(outputs) if r['status']=='ok' and r['final_message'] is not None]
    if n<10: raise ValueError('At least 10 messages are required')
    if len(rows)<n: raise ValueError(f'Only {len(rows)} messages; run more cases before exporting {n}')
    random.Random(seed).shuffle(rows); rows=rows[:n]; out=Path(out); out.mkdir(parents=True,exist_ok=True)
    if (out/'ratings.csv').exists(): raise ValueError('Refusing to overwrite human ratings')
    fields=['blind_id','context','message']+DIMENSIONS+['notes','rated_at','rated_before_viewing_llm_scores']
    mapping={}
    with (out/'ratings.csv').open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=fields); w.writeheader()
        for i,r in enumerate(rows):
            key=f'message_{i+1:03d}';mapping[key]={'case_id':r['case_id'],'config_id':r['config_id'],'is_mock':r.get('is_mock',False)}
            w.writerow({'blind_id':key,'context':json.dumps(r['evaluation_context'],ensure_ascii=False),'message':r['final_message']})
    write_json(out/'private_mapping.json',mapping)
    (out/'RUBRIC.txt').write_text(RUBRIC+'\nComplete ratings independently BEFORE viewing judge scores. Enter yes in the attestation column and an ISO timestamp. Do not share private_mapping.json with raters.\n',encoding='utf-8')
