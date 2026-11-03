"""Deterministic provenance checks shared by all experimental configurations.

These checks catch invalid references and a narrow class of stale deadline claims;
they do not establish semantic correctness of arbitrary natural-language statements.
"""
import hashlib,json,re
from datetime import datetime,timedelta
from zoneinfo import ZoneInfo
from ..io import epoch
NY=ZoneInfo('America/New_York')

def evidence_id(participant,field,value):
    raw=json.dumps([participant,field,value],sort_keys=True,ensure_ascii=False)
    return 'ev_'+hashlib.sha256(raw.encode()).hexdigest()[:12]

def compact_context(result,row):
    cutoff=epoch(row['decision_time']);day=datetime.fromtimestamp(cutoff,NY).date()
    participant=row['participant_id'];obs=result['observations']
    ema=obs.get('ema',{})
    for field,item in ema.get('latest',{}).items():
        item['id']=evidence_id(participant,field,item)
        source=item.get('source','EMA/'+field.split('.')[0]);item['source']=source
        stamp=datetime.fromtimestamp(epoch(item['observed_at']),NY)
        question=item.get('question','').strip()
        item['reported_local']=stamp.isoformat()
        item['age_hours']=round((cutoff-epoch(item['observed_at']))/3600,1)
        item.pop('source_file',None);item.pop('field',None);item.pop('code',None)
        # Local time retains an explicit offset; avoid repeating a second timestamp.
        item.pop('observed_at',None)
        if field=='Class.due' or 'today' in question.lower():
            item['reference_date']=stamp.date().isoformat()
            item['applies_to_decision_day']=stamp.date()==day
            item['time_scope']='response_day'
        elif field in ('Sleep.hour','Sleep.rate'):
            item['time_scope']='retrospective_sleep_report_exact_night_unverified'
        elif 'yesterday' in question.lower():
            item['reference_date']=(stamp.date()-timedelta(days=1)).isoformat()
            item['time_scope']='yesterday_relative_to_response_date'
        elif field=='Mood 1.tomorrow':
            item['time_scope']='prediction_not_observed_future_mood'
        else:item['time_scope']='report_at_submission_time'
        short={'Social.number':'Reported contact count category for yesterday.',
               'Sleep.social':'Trouble staying awake yesterday, not social contact.',
               'Class.due':'Assignment, quiz or exam due on response day (not necessarily decision day).'}
        if field in short:item['question']=short[field]
    for field,summary in ema.get('history_summary',{}).items():
        summary['id']=evidence_id(participant,'history:'+field,[row['decision_time'],summary])
        summary['source']='EMA/history/'+field
        summary.pop('last_responses',None)
    for section in ('sensing','optional'):
        for field,item in obs.get(section,{}).items():
            item['id']=evidence_id(participant,section+':'+field,[row['decision_time'],item])
            item['source']=section+'/'+field
    # Values already appear in observations. One authoritative copy prevents
    # duplication on every planner/draft/reviewer call.
    result.pop('evidence',None)
    result['provenance']={k:v for k,v in result['provenance'].items() if k not in ('intentionally_excluded','simulated_profiles_not_included')}
    result['context_format']='compact-grounded-v1'
    result['decision_local_date']=day.isoformat()
    return result

def registry(context):
    found={}
    def visit(value):
        if isinstance(value,dict):
            if isinstance(value.get('id'),str) and 'source' in value:found[value['id']]=value
            for v in value.values():visit(v)
        elif isinstance(value,list):
            for v in value:visit(v)
    visit(context.get('extended_observations',{}).get('observations',{}))
    return found

# Deliberately narrow: general offers of help "today" are not deadline claims.
TODAY_DUE=re.compile(r'\b(?:due|deadlines?)\b[^.!?\n]{0,25}\btoday\b|\btoday(?:[\x27’]s)?\b[^.!?\n]{0,25}\b(?:due|deadlines?)\b',re.I)

def asserted_deadline_today(text):
    for sentence in re.findall(r'[^.!?\n]+[.!?]?',text):
        if sentence.rstrip().endswith('?') and re.match(r'\s*(do|does|are|is|what|any|could|would|can|have|which)\b',sentence,re.I):continue
        if re.search(r"\b(unknown|unsure|unclear)\b|cannot confirm|don't know|do not know",sentence,re.I):continue
        if TODAY_DUE.search(sentence):return True
    return False

def grounding_issues(draft,context):
    ext=context.get('extended_observations',{})
    if ext.get('context_format')!='compact-grounded-v1':return []
    known=registry(context);issues=[]
    original={r['id']:r for entry in context.get('observations',{}).values() if isinstance(entry,dict) for r in entry.get('observations',[]) if 'id' in r}
    known.update(original)
    for evidence in draft.get('evidence',[]):
        source=evidence.get('source','');identifier=evidence.get('id')
        other_sources={'missing_data','authored_skill','simulated_resource',context.get('profile',{}).get('source','simulated_profile')}
        other_sources.update(e.get('source') for e in context.get('history',[]))
        if source not in other_sources or identifier in known:
            if identifier not in known:
                issues.append('Unknown observation evidence ID: '+str(identifier))
            elif source!=known[identifier]['source']:
                issues.append('Evidence source does not match ID '+identifier)
    due=ext.get('observations',{}).get('ema',{}).get('latest',{}).get('Class.due')
    texts=[draft.get('final_message') or '']+[e.get('detail','') for e in draft.get('evidence',[])]
    if due and not due.get('applies_to_decision_day',False) and any(asserted_deadline_today(t) for t in texts):
        issues.append('Class.due concerns '+due.get('reference_date','an earlier date')+'; it does not establish deadlines today. Use dated wording or say today is unknown.')
    return sorted(set(issues))
