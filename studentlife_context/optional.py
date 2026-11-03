"""Conservative adapters for undocumented streams: metadata coverage only."""
from __future__ import annotations
from pathlib import Path
from .common import participant_files, read_records, record_time, safe_window, iso

# Excludes end-of-term education, unverified surveys, and private communication
# content. They can be added later ONLY after inspecting their actual schemas.
OPTIONAL_STREAMS=('calendar','app_usage')
EXCLUDED_STREAMS={'education/grades,class,piazza':'Possible post-decision grades/GPA or undocumented historical semantics.',
                  'survey':'Questionnaire schema and measurement timing not validated.',
                  'call_log':'Private communication metadata; not necessary for first version.',
                  'sms':'Private message data; not necessary for first version.',
                  'dinning':'Text-file format and semantics not validated.'}


def summarize_optional(dataset_root:Path,participant:str,decision_time:float,
                       days:float=7,enabled=None):
    enabled=set(enabled or OPTIONAL_STREAMS)
    out={}
    for stream in OPTIONAL_STREAMS:
        if stream not in enabled:continue
        paths=list(participant_files(dataset_root/stream,participant))
        if not paths: continue
        count=0; latest=None; ignored_future=0
        for f in paths:
            for record in read_records(f):
                ts=record_time(record)
                if ts is not None and ts>decision_time:
                    ignored_future+=1
                if not safe_window(ts,decision_time,days):continue
                # Calendar future schedule, class titles, app names, meal venues,
                # etc. are intentionally not passed without validated semantics.
                count+=1; latest=ts if latest is None else max(latest,ts)
        out[stream]={'timestamped_rows_last_days':count,'window_days':days,
                     'last_observation':iso(latest) if latest else None,
                     'excluded_future_rows':ignored_future,
                     'note':'Coverage only: no unverified values or personal text used.'}
    return out
