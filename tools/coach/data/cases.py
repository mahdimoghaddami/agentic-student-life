from ..io import epoch,iso

def build_cases(records,profiles,hour=9,limit=100):
    from datetime import datetime,timedelta
    from zoneinfo import ZoneInfo
    zone=ZoneInfo('America/New_York'); cases=[]
    for participant in sorted(profiles):
        rows=[r for r in records if r['participant_id']==participant]
        dates=sorted({datetime.fromtimestamp(epoch(r['available_at']),zone).date()+timedelta(days=1) for r in rows})
        for date in dates:
            t=datetime.combine(date,datetime.min.time(),tzinfo=zone).replace(hour=hour)
            cases.append({'case_id':f'{participant}_{date}','participant_id':participant,'decision_time':t.isoformat(),'profile':profiles[participant],'history':[],'case_kind':'naturalistic','acceptable_decisions':[]})
    # Round-robin chronological selection avoids filling a small limit with one participant.
    return sorted(cases,key=lambda c:(epoch(c['decision_time']),c['participant_id']))[:limit]

def validate_cases(cases):
    ids=set()
    for c in cases:
        for k in ('case_id','participant_id','decision_time','profile','history'):
            if k not in c: raise ValueError('Missing case field '+k)
        if c['case_id'] in ids: raise ValueError('Duplicate case ID')
        ids.add(c['case_id']); epoch(c['decision_time'])
        if 'source' not in c['profile']: raise ValueError('Profile provenance required')
        for e in c['history']:
            for k in ('id','at','kind','source'):
                if k not in e: raise ValueError('History event missing '+k)
            epoch(e['at'])
    return cases
