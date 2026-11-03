"""Summarize execution/design-pattern evidence without asserting message quality."""
import argparse,json
from pathlib import Path
from collections import Counter
p=argparse.ArgumentParser();p.add_argument('--run',required=True);a=p.parse_args();root=Path(a.run)
def read(name):return [json.loads(l) for l in (root/name).read_text().splitlines() if l.strip()]
rows=read('outputs.jsonl');traces=read('traces.jsonl')
result={'cases':len(rows),'successful':sum(r['status']=='ok' for r in rows),
        'messages':sum(r['status']=='ok' and r.get('final_message') is not None for r in rows),
        'decisions':dict(Counter(r.get('decision') for r in rows if r['status']=='ok')),
        'models':sorted(set(str(r.get('provider'))+'/'+str(r.get('model')) for r in rows)),
        'mock_cases':sum(r.get('is_mock',False) for r in rows),
        'tool_calls':dict(Counter(e['name'] for t in traces for e in t['events'] if e['type']=='tool')),
        'planning_rounds':dict(Counter(r['trace']['planning_rounds'] for r in rows)),
        'reflection_cycles':dict(Counter(r['trace']['reflection_cycles'] for r in rows)),
        'cases_with_history':sum(bool(r.get('evaluation_context',{}).get('history')) for r in rows),
        'failed':[{'case_id':r['case_id'],'error':r.get('error')} for r in rows if r['status']!='ok']}
print(json.dumps(result,indent=2))
