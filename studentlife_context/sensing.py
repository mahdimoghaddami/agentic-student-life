"""Privacy-preserving, time-gated summaries of passive sensing streams."""
from __future__ import annotations
from collections import Counter
from pathlib import Path
from .common import END_KEYS, record_time, read_records, participant_files, iso, safe_window

PASSIVE_STREAMS=('activity','conversation','phonelock','phonecharge','dark',
                 'audio','bluetooth','wifi','wifi_location','gps')
DEFAULT_SENSING=('activity','conversation','phonelock','phonecharge','dark')
# Labels are read literally; no numerical-code mapping without a codebook.
ACTIVITY_VALUE_KEYS=('activity_inference','activity','inference','activity_type','state','label')
AUDIO_VALUE_KEYS=('audio_inference','audio','inference')
ACTIVITY_CODES={'0':'stationary','1':'walking','2':'running','3':'unknown'}
AUDIO_CODES={'0':'silence','1':'voice','2':'noise','3':'unknown'}
INTERVAL_STREAMS={'conversation','phonecharge','phonelock','dark'}


def _join(intervals):
    """Merge duplicates/overlap; sum only observed completed intervals."""
    intervals=sorted(set(intervals))
    if not intervals:return 0.0
    start,end=intervals[0]; total=0.0
    for a,b in intervals[1:]:
        if a<=end: end=max(end,b)
        else: total+=end-start; start,end=a,b
    return total+end-start


def summarize_sensing(dataset_root:Path,participant:str,decision_time:float,
                      hours:float=24,enabled=None):
    enabled=set(DEFAULT_SENSING if enabled is None else enabled)
    begin=decision_time-hours*3600
    results={}
    for stream in PASSIVE_STREAMS:
        if stream not in enabled: continue
        paths=list(participant_files(dataset_root/'sensing'/stream,participant))
        if not paths: continue
        samples=0; labels=Counter(); intervals=[]; latest=None; future=0; invalid=0
        for path in paths:
            for rec in read_records(path):
                ts=record_time(rec)
                if ts is None:
                    invalid+=1
                    continue
                if ts>decision_time:
                    future+=1
                    continue
                if stream in INTERVAL_STREAMS:
                    end=record_time(rec,END_KEYS)
                    if end is None or end<=ts or end>decision_time:
                        invalid+=1
                        continue
                    # Include completed intervals overlapping the lookback boundary.
                    if end<=begin:continue
                    intervals.append((max(begin,ts),end))
                elif not safe_window(ts,decision_time,hours/24):
                    continue
                samples+=1
                available=end if stream in INTERVAL_STREAMS else ts
                latest=available if latest is None else max(latest,available)
                if stream=='activity':
                    for key in ACTIVITY_VALUE_KEYS:
                        if key in rec and str(rec[key]).strip():
                            raw=str(rec[key]).strip().lower()
                            label=ACTIVITY_CODES.get(raw,raw)
                            if label in {'walking','running','stationary','sitting','standing','unknown'}:
                                labels[label]+=1
                            break
                if stream=='audio':
                    for key in AUDIO_VALUE_KEYS:
                        if key in rec and str(rec[key]).strip():
                            raw=str(rec[key]).strip().lower()
                            label=AUDIO_CODES.get(raw,raw)
                            if label in {'voice','silence','noise','unknown'}:labels[label]+=1
                            break
        item={'rows_last_hours':samples,'window_hours':hours,
              'last_observation':iso(latest) if latest is not None else None,
              'missing':samples==0,'excluded_future_rows':future,
              'invalid_rows':invalid}
        if stream in INTERVAL_STREAMS:
            key={'conversation':'detected_conversation_minutes',
                 'phonecharge':'recorded_charging_minutes',
                 'phonelock':'recorded_locked_minutes',
                 'dark':'recorded_dark_minutes'}[stream]
            item[key]=round(_join(intervals)/60,2) if samples else None
            item['interpretation']={
                'conversation':'Sensor-detected conversation; not conversation content or social well-being.',
                'phonecharge':'Recorded charging interval duration, not time asleep.',
                'phonelock':'Recorded phone-locked interval duration, not screen-on time or sleep.',
                'dark':'Recorded darkness intervals, not time asleep.'}[stream]
        elif stream in {'activity','audio'}:
            item['decoded_classification_sample_counts']=dict(sorted(labels.items()))
            item['interpretation']=('Counts are sampled activity classifications, not minutes of activity.'
                                    if stream=='activity' else
                                    'Counts are sampled audio inferences, not speech recordings or conversation durations.')
        elif stream=='gps':
            item['interpretation']='GPS fix coverage only; coordinates and spatial trails withheld.'
        else:
            item['interpretation']='Time-stamped sensor row count/coverage only; no identities or inferred health.'
        results[stream]=item
    return results
