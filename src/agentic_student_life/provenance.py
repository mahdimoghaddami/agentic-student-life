"""Prevent resumed experiments from mixing code, models, data, or case definitions."""
import hashlib
import json
from pathlib import Path

PROTOCOL_VERSION = 2
ROOT = Path(__file__).resolve().parents[2]


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str).encode()).hexdigest()


def source_digest():
    paths = [p for folder in ("src", "prompts", "skills", "resources")
             for p in (ROOT / folder).rglob("*") if p.is_file()
             and p.suffix in (".py", ".md", ".json")]
    return digest({p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                   for p in sorted(paths)})


def run_manifest(cfg, cases, profiles, cache_dir):
    cache = Path(cache_dir)
    files = [cache / name for name in ("academic.json", "surveys.json")]
    for uid in sorted({c["participant_id"] for c in cases}):
        files.extend(cache / f"{kind}_{uid}.parquet" for kind in ("daily", "ema"))
    data = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in files if p.exists()}
    metadata = {"protocol_version": PROTOCOL_VERSION, "config": cfg.to_dict(),
                "cases": cases, "profiles": profiles, "source_digest": source_digest(),
                "data_digest": digest(data)}
    return {"protocol_version": PROTOCOL_VERSION, "fingerprint": digest(metadata),
            "source_digest": metadata["source_digest"], "data_digest": metadata["data_digest"],
            "model": cfg.model, "case_ids": [c["case_id"] for c in cases]}
