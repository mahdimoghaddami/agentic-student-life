"""EMA decoding using the dataset's own codebook, not ordinal guesses."""
from __future__ import annotations
import json
import re
from pathlib import Path
from collections import Counter
from datetime import datetime
from zoneinfo import ZoneInfo
from .common import iso, participant_files, read_records, record_time, safe_window, source_name

# Full survey/field names avoid collisions (Sleep.social != Social.number).
FIELDS = {
    'Sleep': ('hour','rate','social'),
    'Stress': ('level',),
    'Mood': ('happyornot','happy','sadornot','sad'),
    'Mood 1': ('tomorrow',),
    'Mood 2': ('how',),
    'Exercise': ('have','schedule','exercise','walk'),
    'Social': ('number',),
    'Activity': ('working','relaxing','other_working','other_relaxing'),
    'Class': ('experience','hours','due'),
    'Class 2': ('challenge','effort','grade'),
    'Study Spaces': ('productivity','noise'),
    'Behavior': ('enthusiastic','critical','dependable','anxious','experiences',
                 'reserved','sympathetic','disorganized','calm','conventional'),
    'Events': ('positive','negative'),
    'Dining Halls': ('breakfast','lunch','dinner'),
    'Lab': ('enjoy','duration'),
}
BRACKET_CODE = re.compile(r'\[(\d+)\]\s*(.*?)(?=\s*,?\s*\[\d+\]|\s*$)', re.S)


def option_map(option_string):
    """Handle [1]label, yes/no and 1..5 Likert formats."""
    s=(option_string or '').strip()
    found=BRACKET_CODE.findall(s)
    if found:
        return {code:label.strip(' \t\r\n,') for code,label in found}
    if '(Yes)' in s and '(No)' in s:
        return {'1':'Yes','2':'No'}
    if '1 2 3 4 5' in s and '(Extremely)' in s:
        return {'1':'Not at all','2':'A little','3':'Somewhat',
                '4':'Very','5':'Extremely'}
    return {}


def load_codebook(dataset_root: Path):
    path=dataset_root/'EMA'/'EMA_definition.json'
    if not path.is_file():
        raise FileNotFoundError(f'Missing required EMA codebook: {path}')
    definitions=json.loads(path.read_text(encoding='utf-8-sig'))
    book={}
    for survey in definitions:
        name=survey.get('name')
        if not name: continue
        book[name]={}
        for q in survey.get('questions',[]):
            field=q.get('question_id')
            if field:
                book[name][field]={'options':option_map(q.get('options','')),
                                   'question':q.get('question_text','')}
    return book


def decode(survey,field,value,book):
    if value is None or isinstance(value,(list,dict)): return None
    code=str(value).strip()
    if code.lower() in {'','none','null','nan'}: return None
    options=book.get(survey,{}).get(field,{}).get('options',{})
    label=options.get(code)
    if label is None:
        raise ValueError(f'Unknown or undefined EMA code for {survey}.{field}: {code}')
    output={'code':code,'label':label}
    if survey=='Sleep' and field=='hour':
        try: output['hours']=float(label)
        except ValueError: pass  # e.g. <3 is censored, not '3 hours'
    return output


def summarize_ema(dataset_root:Path,participant:str,decision_time:float,days:float=7,
                  enabled_surveys=None):
    book=load_codebook(dataset_root)
    latest={}  # field -> latest response, not latest entire survey
    history={}
    counts={'seen':0,'valid':0,'missing_or_unmapped':0,'after_cutoff':0}
    for survey,fields in FIELDS.items():
        if enabled_surveys is not None and survey not in enabled_surveys: continue
        base=dataset_root/'EMA'/'response'/survey
        for file in participant_files(base,participant):
            for rec in read_records(file):
                counts['seen']+=1
                ts=record_time(rec,('resp_time',))
                if ts is not None and ts>decision_time: counts['after_cutoff']+=1
                if not safe_window(ts,decision_time,days): continue
                got=False
                # Conditional answers are usable only with a matching parent in this response.
                conditions={('Mood','happy'):('happyornot','1'),('Mood','sad'):('sadornot','1'),
                            ('Exercise','schedule'):('have','2'),('Exercise','exercise'):('have','1')}
                for field in fields:
                    if field not in rec: continue
                    condition=conditions.get((survey,field))
                    if condition and str(rec.get(condition[0],''))!=condition[1]: continue
                    decoded=decode(survey,field,rec[field],book)
                    if decoded is None: continue
                    got=True
                    key=f'{survey}.{field}'
                    history.setdefault(key,[]).append((ts,decoded))
                    if key not in latest or ts>latest[key]['observed_at_epoch']:
                        latest[key]={'source':f'EMA/{survey}', 'field':field,
                                     'observed_at':iso(ts),'observed_at_epoch':ts,
                                     'age_hours':round((decision_time-ts)/3600,2),
                                     'source_file':source_name(file,dataset_root),
                                     'question':book[survey][field]['question'],**decoded}
                if got: counts['valid']+=1
                else: counts['missing_or_unmapped']+=1
    result={}
    for key,rec in sorted(latest.items()):
        result[key]={k:v for k,v in rec.items() if k!='observed_at_epoch'}
    # Small, time-safe longitudinal summaries; ordinal labels are never averaged.
    ny=ZoneInfo('America/New_York')
    recent={}
    for key,rows in sorted(history.items()):
        unique={(ts,r['code']):(ts,r) for ts,r in rows}
        ordered=sorted(unique.values(),key=lambda x:x[0])
        labels=Counter(r['label'] for _,r in ordered)
        days_seen={datetime.fromtimestamp(ts,ny).date().isoformat() for ts,_ in ordered}
        numeric=[r['hours'] for _,r in ordered if 'hours' in r]
        summary={'response_count':len(ordered),'distinct_response_days':len(days_seen),
                 'category_counts':dict(sorted(labels.items())),
                 'last_responses':[{'observed_at':iso(ts),'label':r['label']} for ts,r in ordered[-4:]]}
        if key=='Sleep.hour' and len(numeric)>=2:
            summary['mean_reported_sleep_hours_exact_categories']=round(sum(numeric)/len(numeric),2)
            summary['numeric_response_count']=len(numeric)
        if key=='Sleep.hour':
            from statistics import median
            previous=[r['hours'] for _,r in ordered[:-1] if 'hours' in r]
            baseline=median(previous) if previous else None
            last_hours=ordered[-1][1].get('hours')
            summary['prior_median_hours']=baseline
            summary['difference_from_prior_median']=last_hours-baseline if last_hours is not None and baseline is not None else None
        recent[key]=summary
    return {'latest':result,'history_summary':recent,'quality':counts}
