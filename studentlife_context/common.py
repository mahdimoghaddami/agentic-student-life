"""Shared file readers and time parsing. No external dependencies."""
from __future__ import annotations
import csv
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

LOCAL_TZ = ZoneInfo('America/New_York')
TIME_KEYS = ('resp_time','timestamp','start_timestamp','start_time','time_start','start','datetime','date','time')
END_KEYS = ('end_timestamp','end_time','time_end','end','stop_timestamp','stop_time')


def timestamp(value):
    """Seconds since epoch; reject bare clock-times and implausible dates."""
    if value is None or isinstance(value,bool):
        return None
    if isinstance(value,(int,float)) or (isinstance(value,str) and re.fullmatch(r'\d+(?:\.\d+)?',value.strip())):
        try:
            n=float(value)
            if n > 1e12: n/=1000
            return n if 946684800 <= n <= 4102444800 else None
        except (TypeError,ValueError,OverflowError): return None
    if not isinstance(value,str): return None
    try:
        dt=datetime.fromisoformat(value.strip().replace('Z','+00:00'))
        if dt.tzinfo is None: dt=dt.replace(tzinfo=LOCAL_TZ)
        out=dt.timestamp()
        return out if 946684800 <= out <= 4102444800 else None
    except (ValueError,OverflowError): return None


def record_time(record, keys=TIME_KEYS):
    for key in keys:
        if key in record:
            ts=timestamp(record[key])
            if ts is not None: return ts
    return None


def iso(ts):
    return datetime.fromtimestamp(ts, timezone.utc).isoformat(timespec='seconds')


def read_records(path):
    """Yield dictionaries from CSV, JSON array/object or JSONL; skip unreadable records."""
    try:
        if path.suffix.lower()=='.csv':
            with path.open(encoding='utf-8-sig',newline='') as f:
                for item in csv.DictReader(f):
                    if item: yield {re.sub(r'\s+', '_', k.strip().lower()):v for k,v in item.items() if k}
        elif path.suffix.lower()=='.json':
            with path.open(encoding='utf-8-sig') as f: obj=json.load(f)
            if isinstance(obj,list): items=obj
            elif isinstance(obj,dict):
                nested=next((obj[k] for k in ('data','responses','records','events') if isinstance(obj.get(k),list)),None)
                items=nested if nested is not None else [obj]
            else: items=[]
            for item in items:
                if isinstance(item,dict): yield item
        elif path.suffix.lower()=='.jsonl':
            with path.open(encoding='utf-8-sig') as f:
                for line in f:
                    try: item=json.loads(line)
                    except json.JSONDecodeError as exc: raise ValueError(f"Malformed JSONL: {path}") from exc
                    if isinstance(item,dict): yield item
    except (OSError,UnicodeError,ValueError,csv.Error) as exc:
        raise ValueError(f"Cannot parse selected data file: {path}") from exc


def participant_files(root: Path, participant: str):
    """Match anonymous ID as a filename token, never u01 within u010."""
    token=re.compile(r'(?<![a-zA-Z0-9])'+re.escape(participant)+r'(?![a-zA-Z0-9])',re.I)
    if not root.exists(): return
    for p in sorted(root.rglob('*')):
        if p.is_file() and p.suffix.lower() in {'.csv','.json','.jsonl'} and token.search(p.stem):
            yield p


def safe_window(ts, decision_time, days):
    return ts is not None and decision_time-days*86400 <= ts <= decision_time


def source_name(path, dataset_root):
    return str(path.relative_to(dataset_root)).replace('\\','/')
