from statistics import median
from collections import Counter
from ..io import epoch

def merge_minutes(intervals):
    total=0.; end=None
    for a,b in sorted(set((float(a),float(b)) for a,b in intervals)):
        if b<a: raise ValueError("Negative interval")
        total+=max(0,b-max(a,end if end is not None else a)); end=max(b,end if end is not None else b)
    return total/60

def summarize(records, participant, decision_time, days=7):
    t=epoch(decision_time); start=t-days*86400
    available=[r for r in records if r['participant_id']==participant and epoch(r['available_at'])<=t and epoch(r['observed_at'])<=t and (not r.get('end_at') or epoch(r['end_at'])<=t)]
    result={}
    for stream in ('sleep','stress','activity','conversation'):
        rows=sorted([r for r in available if r['stream']==stream and epoch(r.get('end_at',r['observed_at']))>=start],key=lambda r:epoch(r['available_at']))
        entry={'observations':rows[-4:],'observations_truncated':len(rows)>4,'count':len(rows),'missing':not rows,'window_days':days}
        if rows:
            latest=rows[-1]; entry.update(latest=latest,age_hours=(t-epoch(latest['available_at']))/3600)
            if stream=='sleep':
                previous=[r['value'] for r in rows[:-1] if isinstance(r['value'],(int,float))]
                entry['prior_median_hours']=median(previous) if previous else None
                entry['difference_from_prior_median']=latest['value']-median(previous) if previous and isinstance(latest['value'],(int,float)) else None
            elif stream=='activity':
                counts=Counter(str(r['value']) for r in rows)
                entry['sample_proportions']={k:v/len(rows) for k,v in counts.items()}
                entry['limitation']='Sample proportions are not activity durations.'
            elif stream=='conversation':
                entry['detected_minutes']=merge_minutes([(max(start,epoch(r['observed_at'])),epoch(r['end_at'])) for r in rows])
                entry['limitation']='Detection does not establish loneliness or conversational content; coverage is unknown.'
        result[stream]=entry
    return result

def validate_records(records):
    ids=set()
    for r in records:
        for k in ('id','participant_id','stream','observed_at','available_at','value','source'): 
            if k not in r: raise ValueError(f"Missing observation field {k}")
        if r['id'] in ids: raise ValueError('Duplicate observation id')
        ids.add(r['id']); epoch(r['available_at']); epoch(r['observed_at'])
        if r['stream'] not in ('sleep','stress','activity','conversation'): raise ValueError('Unknown stream')
        if r['stream']=='conversation':
            if epoch(r['end_at'])<epoch(r['observed_at']): raise ValueError('Negative interval')
    return records
