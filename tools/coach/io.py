import json, os
from pathlib import Path
from datetime import datetime, timezone

def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))
def read_jsonl(path):
    return [json.loads(x) for x in Path(path).read_text(encoding="utf-8").splitlines() if x.strip()]
def write_json(path, obj):
    p=Path(path); p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
def write_jsonl(path, rows):
    p=Path(path); p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("".join(json.dumps(x,ensure_ascii=False)+"\n" for x in rows),encoding="utf-8")
def epoch(value):
    if isinstance(value,(int,float)): return float(value)
    try: return float(value)
    except (TypeError,ValueError): pass
    d=datetime.fromisoformat(value.replace("Z","+00:00"))
    if d.tzinfo is None: raise ValueError("Timestamps must include a timezone")
    return d.timestamp()
def iso(value): return datetime.fromtimestamp(epoch(value),timezone.utc).isoformat()
def load_env(path=".env"):
    if not Path(path).exists(): return
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        line=line.strip()
        if not line or line.startswith("#"): continue
        k,v=line.split("=",1); os.environ.setdefault(k.strip(),v.strip().strip('"').strip("'"))
