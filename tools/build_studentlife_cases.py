"""Create naturalistic cases from EMA response dates without guessing user preferences."""
import argparse,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from datetime import datetime,timedelta,time
from zoneinfo import ZoneInfo
from studentlife_context.ema import FIELDS,load_codebook,decode
from studentlife_context.common import participant_files,read_records,record_time
from coach.io import write_jsonl

def main():
    p=argparse.ArgumentParser();p.add_argument('--root',default='dataset');p.add_argument('--out',default='data/cases.real.jsonl');p.add_argument('--limit',type=int,default=16);p.add_argument('--participants',nargs='+',required=True)
    a=p.parse_args()
    if a.limit<1:p.error('--limit must be positive')
    root=Path(a.root);book=load_codebook(root);zone=ZoneInfo('America/New_York');cases=[]
    for participant in a.participants:
        dates=set()
        for survey,fields in FIELDS.items():
            for path in participant_files(root/'EMA/response'/survey,participant):
                for row in read_records(path):
                    ts=record_time(row,('resp_time',))
                    if ts is None:continue
                    if not any(field in row and decode(survey,field,row[field],book) for field in fields):continue
                    dates.add(datetime.fromtimestamp(ts,zone).date()+timedelta(days=1))
        for day in sorted(dates):
            cases.append({'case_id':f'{participant}_{day}','participant_id':participant,
                'decision_time':datetime.combine(day,time(9),zone).isoformat(),
                'profile':{'source':'simulated_profile','goal':'Optional everyday study and well-being support; preferences unknown'},
                'history':[],'case_kind':'naturalistic','acceptable_decisions':[]})
    cases=sorted(cases,key=lambda c:(c['decision_time'],c['participant_id']))[:a.limit]
    if not cases:raise ValueError('No valid EMA response dates for selected participants')
    write_jsonl(a.out,cases);print(f'Wrote {len(cases)} cases to {a.out}; review simulated profiles before evaluation')
if __name__=='__main__':main()
