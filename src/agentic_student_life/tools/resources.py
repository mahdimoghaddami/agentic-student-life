"""Curated campus-resource search (static, not personal data -> no leakage risk)."""

from __future__ import annotations

import json
import re
from pathlib import Path

_CANDIDATES = [Path(__file__).resolve().parents[3] / "resources" / "campus_resources.json",
               Path("resources") / "campus_resources.json"]
CRISIS_WORDS = ("crisis", "suicid", "self-harm", "self harm", "hopeless", "kill", "die", "unsafe",
                "emergency", "end it")


def load_resources() -> list[dict]:
    for p in _CANDIDATES:
        if p.exists():
            return json.load(open(p))
    return []


def search_campus_resources(need: str) -> dict:
    """Search a small curated list of Dartmouth campus resources (counseling, health
    service, gym, tutoring, study rooms, crisis lines, student center) for a need.

    Args:
        need: Short description of the need, e.g. "stress counseling", "exercise",
            "tutoring for exams", "crisis", "meet people".

    Returns:
        dict: Up to 3 matching curated resources (name, category, description, contact).
    """
    res = load_resources()
    q = (need or "").lower()
    toks = set(re.findall(r"[a-z\-]+", q))
    scored = []
    for r in res:
        text = " ".join([r["name"], r["category"], r["description"], " ".join(r["keywords"])]).lower()
        s = sum(2 for k in r["keywords"] if k in q) + sum(1 for t in toks if len(t) > 3 and t in text)
        if any(w in q for w in CRISIS_WORDS) and r["category"] == "crisis":
            s += 10
        scored.append((s, r))
    scored.sort(key=lambda x: -x[0])
    hits = [r for s, r in scored if s > 0][:3] or [r for _, r in scored if r["category"] == "mental_health"]
    items = [{k: r[k] for k in ("name", "category", "description", "contact", "curated")} for r in hits]
    return {"source": "curated.resources", "need": need, "results": items,
            "summary": "Curated resources: " + ", ".join(i["name"] for i in items)}

