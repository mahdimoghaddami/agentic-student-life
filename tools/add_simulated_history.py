"""Add clearly labeled reproducible preferences/feedback to real-data case inputs."""
import argparse,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from collections import defaultdict
from coach.io import read_jsonl,write_jsonl,epoch,iso

def main():
    p=argparse.ArgumentParser();p.add_argument('--cases',required=True);p.add_argument('--out',required=True);a=p.parse_args()
    if Path(a.out).exists():raise ValueError('Output exists; use a fresh name')
    rows=read_jsonl(a.cases);groups=defaultdict(list)
    for r in rows:
        if r.get('history'):raise ValueError('Input already has history; refusing to overwrite it')
        groups[r['participant_id']].append(r)
    for pid,cases in sorted(groups.items()):
        cases.sort(key=lambda c:epoch(c['decision_time']))
        for r in cases:r['profile']={'source':'simulated_profile','goals':['Make coursework manageable'],'preferred_activity':'quiet_break','do_not_disturb':False}
        events=[]
        if len(cases)>1:
            events.append({'id':pid+'_sim_preference','at':iso(epoch(cases[1]['decision_time'])-3600),
                'kind':'preference_update','source':'simulated_interaction','updates':{'preferred_activity':'stretching'},
                'detail':'SIMULATED: student now prefers stretching to a quiet break.'})
        if len(cases)>2:
            t=epoch(cases[2]['decision_time'])-3600
            events += [{'id':pid+'_sim_suggestion','at':iso(t-60),'kind':'coach_output','source':'simulated_interaction',
                        'decision':'suggest','message':'SIMULATED prior suggestion: take a stretch break.'},
                       {'id':pid+'_sim_rejection','at':iso(t),'kind':'feedback','source':'simulated_interaction',
                        'value':'rejected','detail':'SIMULATED: no more break suggestions; please help choose a coursework step instead.'}]
        for r in cases:r['history']=[e for e in events if epoch(e['at'])<=epoch(r['decision_time'])]
    write_jsonl(a.out,rows);print(f'Wrote {len(rows)} real-data cases with explicitly simulated profiles/history; IDs/times unchanged.')
if __name__=='__main__':main()
