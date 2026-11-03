from pathlib import Path
from ..models import Model
from ..io import read_jsonl,write_jsonl,write_json
from .rubric import RUBRIC,DIMENSIONS

def judge(outputs,out,provider,model,allow_mock=False):
    client=Model(provider,model)
    if client.provider=='mock' and not allow_mock: raise ValueError('Mock judge requires --allow-mock; scores are not valid evaluation')
    rows=read_jsonl(outputs); results=[]
    for r in rows:
        if r['status']!='ok' or r['final_message'] is None: continue
        result={'case_id':r['case_id'],'config_id':r['config_id'],'is_mock':client.provider=='mock' or r.get('is_mock',False)}
        if r.get('is_mock') and not allow_mock: raise ValueError('Cannot evaluate mock outputs as real results')
        try:
            answer=client.ask('judge',RUBRIC,{'context':r['evaluation_context'],'decision':r['decision'],'message':r['final_message']})
            for d in DIMENSIONS:
                value=answer['scores'][d]
                if type(value)!=int or not 1<=value<=5: raise ValueError('Judge score outside 1..5')
            result.update(answer,status='ok')
        except Exception as e: result.update(status='failed',error=str(e))
        results.append(result)
    out=Path(out); out.mkdir(parents=True,exist_ok=True)
    write_jsonl(out/'judge_scores.jsonl',results)
    write_jsonl(out/'judge_traces.jsonl',client.calls)
    write_json(out/'judge_settings.json',{'provider':client.provider,'model':client.model,'rubric':RUBRIC,'temperature':0})
    return results
