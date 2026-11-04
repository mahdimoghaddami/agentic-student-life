"""Leakage test: no tool output may reveal data after the decision time.

Run: .venv/bin/python tests/test_leakage.py   (requires cache/features from preprocess)
"""

import json
import re
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from agentic_student_life.data.store import DataStore  # noqa: E402
from agentic_student_life.tools import evidence_summary, make_tools  # noqa: E402

CASES = [("u59", "2013-04-20 21:00"), ("u00", "2013-05-02 09:30"), ("u16", "2013-04-10 14:00")]


def all_outputs(view):
    outs = []
    for f in make_tools(view):
        name = f.__name__
        if name == "compare_to_baseline":
            for feat in ("sleep_hours", "active_minutes", "stress", "conversation_minutes"):
                outs.append(f(feat, 3))
        elif name == "search_campus_resources":
            outs.append(f("stress"))
        elif name in ("get_time_context",):
            outs.append(f())
        else:
            outs += [f(1), f(7)]
    outs.append(evidence_summary(view))
    return outs


def test_view_bounds():
    ds = DataStore(str(ROOT / "cache/features"))
    for uid, t in CASES:
        v = ds.get_view(uid, t)
        assert (v.daily["date"] < pd.Timestamp(v.decision_date)).all()
        assert (v.ema["time"] <= v.decision_time).all() if len(v.ema) else True
        full = ds.ema(uid)
        assert len(v.ema) < len(full), "view should drop future EMA rows"


def test_no_future_dates():
    ds = DataStore(str(ROOT / "cache/features"))
    for uid, t in CASES:
        v = ds.get_view(uid, t)
        text = json.dumps(all_outputs(v), default=str)
        assert len(text) > 100
        for d in re.findall(r"20\d\d-\d\d-\d\d", text):
            assert pd.Timestamp(d).date() <= v.decision_date, f"future date {d} leaked for {uid}@{t}"


def test_outputs_change_only_with_past():
    """Tool outputs must be identical whether or not future data exists in the store."""
    ds = DataStore(str(ROOT / "cache/features"))
    uid, t = CASES[0]
    v = ds.get_view(uid, t)
    a = json.dumps(all_outputs(v), default=str, sort_keys=True)
    # truncate the store's data to t and recompute: must be identical
    ds._daily[uid] = ds.daily(uid)[ds.daily(uid)["date"] <= pd.Timestamp(v.decision_date)]
    ds._ema[uid] = ds.ema(uid)[ds.ema(uid)["time"] <= v.decision_time]
    b = json.dumps(all_outputs(ds.get_view(uid, t)), default=str, sort_keys=True)
    assert a == b, "tool outputs depend on future data"


def test_mask():
    ds = DataStore(str(ROOT / "cache/features"))
    v = ds.get_view("u59", "2013-04-20 21:00", mask=["sleep", "conversation"])
    tools = {f.__name__: f for f in make_tools(v)}
    s = tools["get_sleep_summary"](3)
    assert s["status"] == "missing" and "masked" in s["reason"]
    assert "masked" in tools["get_social_summary"](3).get("conversation", "")


def test_output_size():
    ds = DataStore(str(ROOT / "cache/features"))
    for uid, t in CASES:
        for o in all_outputs(ds.get_view(uid, t))[:-1]:
            assert len(json.dumps(o)) < 1500, (uid, t, o.get("source"), len(json.dumps(o)))


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print("PASS", name)

