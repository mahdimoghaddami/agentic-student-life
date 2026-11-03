"""Stable tool API for agents and ablation runners."""
from __future__ import annotations
from pathlib import Path
from .common import timestamp, iso
from .ema import summarize_ema, FIELDS
from .sensing import summarize_sensing, PASSIVE_STREAMS, DEFAULT_SENSING
from .optional import summarize_optional, OPTIONAL_STREAMS, EXCLUDED_STREAMS
from .academics import summarize_deadlines


def build_student_context(dataset_root,participant,decision_time,*,
                          include=('ema','sensing','optional'),
                          ema_surveys=None,sensing_streams=None,optional_streams=None,
                          ema_days=7,sensing_hours=24,optional_days=7,
                          assume_syllabus_known=False):
    """Return machine-readable observations with explicit missingness and provenance.

    This does NOT decide to send a message or invoke an LLM. Use as a tool for the
    monitoring/planning/coaching agents; keep memory/preferences separate.
    """
    root=Path(dataset_root)
    if not root.exists():raise FileNotFoundError(f'Dataset root not found: {root}')
    cutoff=timestamp(decision_time)
    if cutoff is None:raise ValueError('decision_time must be epoch seconds or ISO 8601')
    if ema_days<=0 or sensing_hours<=0 or optional_days<=0:raise ValueError('Lookback windows must be positive')
    include=set(include)
    if include-{'ema','sensing','optional'}:raise ValueError('Unknown include category')
    info={'participant_id':participant,'decision_time':iso(cutoff),
          'observations':{},'evidence':[],'missing_or_unavailable':[],
          'provenance':{'source':'StudentLife observed data',
                        'future_records_prohibited':True,
                        'sensor_availability_assumption':'Sensor sample time or completed interval end is treated as availability; upload time is not provided.',
                        'windows':{'ema_days':ema_days,'sensing_hours':sensing_hours,'optional_days':optional_days},
                        'simulated_profiles_not_included':True,
                        'intentionally_excluded':EXCLUDED_STREAMS}}
    if 'ema' in include:
        e=summarize_ema(root,participant,cutoff,ema_days,ema_surveys)
        info['observations']['ema']=e
        for key,item in e['latest'].items():
            info['evidence'].append({'source':item['source'], 'field':key,
                'observed_at':item['observed_at'],'value':item['label'],
                'hours':item.get('hours'), 'age_hours':item['age_hours']})
        selected=ema_surveys if ema_surveys is not None else FIELDS.keys()
        for survey in selected:
            if not any(key.startswith(survey+'.') for key in e['latest']):
                info['missing_or_unavailable'].append('EMA/'+survey)
    if 'sensing' in include:
        s=summarize_sensing(root,participant,cutoff,sensing_hours,sensing_streams)
        info['observations']['sensing']=s
        selected_sensors=sensing_streams if sensing_streams is not None else DEFAULT_SENSING
        for name in selected_sensors:
            if name not in s:
                info['missing_or_unavailable'].append('sensing/'+name)
        for name,item in s.items():
            if item['missing']:
                info['missing_or_unavailable'].append('sensing/'+name)
            else:
                value={'rows':item['rows_last_hours']}
                if name in ('conversation','phonecharge','phonelock','dark'):
                    value['recorded_interval_minutes'] = (item.get('detected_conversation_minutes')
                        if name=='conversation' else item.get('recorded_charging_minutes')
                        if name=='phonecharge' else item.get('recorded_locked_minutes')
                        if name=='phonelock' else item.get('recorded_dark_minutes'))
                if name in ('activity','audio'):
                    value['decoded_sample_counts']=item['decoded_classification_sample_counts']
                info['evidence'].append({'source':'sensing/'+name,'observed_at':item['last_observation'],
                                         'value':value,'interpretation':item['interpretation']})
    if assume_syllabus_known:
        deadlines=summarize_deadlines(root,participant,cutoff)
        if deadlines is not None:
            info['observations']['assumed_academic_calendar']=deadlines
            if deadlines['status']=='available':
                info['evidence'].append({'source':'education/deadlines.csv',
                                        'observed_at':info['decision_time'],
                                        'value':{'deadlines_today':deadlines['deadline_count_today'],
                                                 'deadlines_next_7_days':deadlines['deadline_count_next_days']},
                                        'assumption':deadlines['assumption']})
    if 'optional' in include:
        info['observations']['optional']=summarize_optional(root,participant,cutoff,optional_days,optional_streams)
        # Keep coverage-only streams out of coaching evidence, since the meaning
        # of a row has not yet been established.
    info['evidence'].sort(key=lambda e:(e['observed_at'] or '',e['source']))
    return info


def coaching_signals(context):
    """Transparent, tentative observations; NOT diagnoses or medical predictions."""
    ema=context.get('observations',{}).get('ema',{}).get('latest',{})
    signals=[]
    sleep=ema.get('Sleep.hour')
    if sleep and sleep.get('hours') is not None and sleep['hours']<6 and sleep['age_hours']<=48:
        signals.append({'type':'recent_short_sleep_report','source':'Sleep.hour',
                        'detail':f"Student reported {sleep['hours']:g} hours of sleep."})
    stress=ema.get('Stress.level')
    if stress and stress['age_hours']<=36 and stress['code'] in {'2','3'}:
        signals.append({'type':'recent_self_reported_stress','source':'Stress.level',
                        'detail':stress['label']})
    due=ema.get('Class.due')
    from datetime import datetime
    from zoneinfo import ZoneInfo
    ny=ZoneInfo('America/New_York')
    same_day=(due is not None and datetime.fromisoformat(due['observed_at']).astimezone(ny).date()
              ==datetime.fromisoformat(context['decision_time']).astimezone(ny).date())
    if due and due['code']=='1' and same_day:
        signals.append({'type':'student_reported_deadline_today','source':'Class.due',
                        'detail':'Student reported a due assignment, quiz or exam today.'})
    return signals
