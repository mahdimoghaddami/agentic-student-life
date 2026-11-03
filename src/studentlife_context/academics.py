"""Opt-in syllabus-like deadline signals from StudentLife's wide deadline table.

IMPORTANT: This historical table has no per-deadline creation timestamps. Use only
with the explicit simulation assumption that a student knew their planned dates
at the beginning of the term. Never use course grades or term GPA here.
"""
from __future__ import annotations
import csv
import re
from datetime import datetime,timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

DATE_COL=re.compile(r'^\d{4}-\d{2}-\d{2}$')


def summarize_deadlines(dataset_root:Path,participant:str,decision_time:float,days:int=7):
    path=Path(dataset_root)/'education'/'deadlines.csv'
    if not path.is_file():return None
    today=datetime.fromtimestamp(decision_time,ZoneInfo('America/New_York')).date()
    output={'source':'education/deadlines.csv',
        'assumption':'SIMULATED: entire historical syllabus deadline calendar was known at decision time.',
        'window_days':days,'today':today.isoformat(),
        'deadline_count_today':0,'deadline_count_next_days':0,
        'daily_counts':{},'status':'no_participant'}
    with path.open(encoding='utf-8-sig',newline='') as f:
        reader=csv.DictReader(f)
        if not reader.fieldnames:return output
        id_field=next((x for x in reader.fieldnames if x.strip().lower() in ('uid','user_id','participant_id')),None)
        if id_field is None:return output
        for row in reader:
            if (row.get(id_field) or '').strip().lower()!=participant.lower():continue
            output['status']='available'
            for i in range(days+1):
                day=today+timedelta(days=i)
                raw=row.get(day.isoformat())
                if raw is None: continue
                try: value=int(raw.strip())
                except (ValueError,TypeError):continue
                if value<0: continue
                output['daily_counts'][day.isoformat()]=value
                if i==0:output['deadline_count_today']=value
                else:output['deadline_count_next_days']+=value
            break
    return output
