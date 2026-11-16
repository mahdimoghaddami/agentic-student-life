"""Helpers to pick evaluation cases from the preprocessed features."""

from __future__ import annotations

import pandas as pd

from ..data.store import DataStore


def coverage_table(cache_dir: str = "cache/features") -> pd.DataFrame:
    """Per-uid coverage counts, ranked by a coverage score
    (EMA stress responses + days with sleep/activity/conversation)."""
    ds = DataStore(cache_dir)
    rows = []
    for uid in ds.uids():
        d, e = ds.daily(uid), ds.ema(uid)
        rows.append({"uid": uid,
                     "ema_stress": int((e["type"] == "stress").sum()) if len(e) else 0,
                     "ema_total": int(len(e)),
                     "comments": int((e["type"] == "comment").sum()) if len(e) else 0,
                     "sleep_days": int(d["has_sleep"].sum()),
                     "activity_days": int(d["has_activity"].sum()),
                     "conversation_days": int(d["has_conversation"].sum()),
                     "pre_surveys": len(ds.surveys.get(uid, {})) > 0})
    t = pd.DataFrame(rows)
    t["score"] = t["ema_stress"] + t["sleep_days"] + t["activity_days"] + t["conversation_days"]
    return t.sort_values("score", ascending=False).reset_index(drop=True)


def candidate_days(uid: str, cache_dir: str = "cache/features", hour: int = 20) -> pd.DataFrame:
    """Daily rows (one decision time per day at `hour`:00) with case-selection flags:
    high_stress (EMA stress >= 4 in the 48h before the decision time), deadline_soon,
    doing_fine (48h stress mean <= 2.5 and max <= 3, >= 6.5h sleep last night, no deadline
    today and <= 1 in the next 3 days), natural_gap
    (sensing missing on >= 2 of the 3 prior days)."""
    ds = DataStore(cache_dir)
    d = ds.daily(uid).copy()
    e = ds.ema(uid)
    st = e[e["type"] == "stress"] if len(e) else e
    out = []
    for i, r in d.iterrows():
        t = pd.Timestamp(r["date"]).tz_localize("America/New_York") + pd.Timedelta(hours=hour)
        w = st[(st["time"] <= t) & (st["time"] > t - pd.Timedelta(hours=48))] if len(st) else st
        prior = d[(d["date"] < r["date"]) & (d["date"] >= r["date"] - pd.Timedelta(days=3))]
        sensed = (prior["has_activity"] | prior["has_sleep"]).sum() if len(prior) else 0
        max_st = w["stress"].max() if len(w) else None
        low = bool(len(w) and w["stress"].mean() <= 2.5)
        out.append({"date": r["date"].date(), "decision_time": t.strftime("%Y-%m-%d %H:%M"),
                    "term_week": r["term_week"], "stress_48h_max": max_st,
                    "stress_48h_n": len(w), "stress_48h_low": low, "sleep_last_night": r["sleep_hours_inferred"],
                    "deadlines_today": r["deadlines_today"], "deadlines_next_3d": r["deadlines_next_3d"],
                    "high_stress": bool(max_st is not None and max_st >= 4),
                    "deadline_soon": bool(r["deadlines_today"] + r["deadlines_next_3d"] > 0),
                    "natural_gap": bool(3 - sensed >= 2 and r["term_week"] >= 2)})
    c = pd.DataFrame(out)
    c["doing_fine"] = (c["stress_48h_max"].fillna(9) <= 3) & (c["stress_48h_low"]) \
        & (c["sleep_last_night"].fillna(0) >= 6.5) & (c["deadlines_today"] == 0) \
        & (c["deadlines_next_3d"] <= 1)
    return c


if __name__ == "__main__":
    pd.set_option("display.width", 200)
    print(coverage_table().head(10).to_string())
