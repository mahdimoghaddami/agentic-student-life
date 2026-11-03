from pathlib import Path
import sys,platform,hashlib,os
from .io import read_jsonl,write_json,epoch
from .data.features import validate_records
from .data.cases import validate_cases
from .memory import Memory
from .orchestrator import run_case

def run(cases_path,observations_path,config,out,episodes=False,contexts_path=None):
    cases=validate_cases(read_jsonl(cases_path)); records=validate_records(read_jsonl(observations_path)) if observations_path else []
    from .data.contexts import load_contexts
    contexts=load_contexts(contexts_path,cases) if contexts_path else {}
    out=Path(out)
    if out.exists() and any(out.iterdir()): raise ValueError('Output directory must be empty; choose a new run directory')
    out.mkdir(parents=True,exist_ok=True)
    if episodes:
        cases=sorted(cases,key=lambda c:(c.get('episode_id',c['participant_id']),epoch(c['decision_time'])))
        keys=[(c.get('episode_id',c['participant_id']),c['participant_id'],epoch(c['decision_time'])) for c in cases]
        if len(set(keys))!=len(keys): raise ValueError('Episode cases must have distinct decision times per participant')
    manifest={'config':config.to_dict(),'episodes':episodes,'python':sys.version,'platform':platform.platform(),'inputs':{str(p):hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in (cases_path,observations_path) if p is not None}}
    if contexts_path: manifest['inputs'][str(contexts_path)]=hashlib.sha256(Path(contexts_path).read_bytes()).hexdigest()
    manifest['implementation_sha256']={name:hashlib.sha256((Path(__file__).parent/name).read_bytes()).hexdigest() for name in ('prompts.py','orchestrator.py','data/contexts.py','data/grounding.py','models.py','credentials.py','key_pool.py')}
    manifest['credential_policy']={k:os.getenv(k,d) for k,d in [('GEMINI_KEY_MODE','manual'),('GEMINI_MIN_INTERVAL_SECONDS','6'),('GEMINI_MAX_RETRIES','3'),('GEMINI_MAX_RETRY_WAIT_SECONDS','120')]}
    manifest['grounding_policy']='compact-grounded-v1' if contexts_path else 'legacy'
    write_json(out/'manifest.json',manifest)
    memory=Memory(out/'memory.sqlite'); rows=[]
    import json
    try:
        with (out/'outputs.jsonl').open('w',encoding='utf-8') as outputs,(out/'traces.jsonl').open('w',encoding='utf-8') as traces:
            for case in cases:
                scope=case.get('episode_id',case['participant_id']) if episodes else case['case_id']
                row,trace=run_case(case,records,config,memory,scope,contexts.get(case['case_id']))
                outputs.write(json.dumps(row,ensure_ascii=False)+'\n'); outputs.flush()
                traces.write(json.dumps(trace,ensure_ascii=False)+'\n'); traces.flush(); rows.append(row)
                print(f"{case['case_id']}: {row['status']} {row['decision'] or row['error']}")
    finally: memory.close()
    summary={'cases':len(rows),'successful':sum(r['status']=='ok' for r in rows),'failed':[{'case_id':r['case_id'],'error':r['error']} for r in rows if r['status']!='ok']}
    write_json(out/'execution_summary.json',summary); return summary
