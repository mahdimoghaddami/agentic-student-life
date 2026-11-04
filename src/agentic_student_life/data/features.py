"""Deterministic feature caches. Daily sensing is available after the day closes."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from .loaders import TERM_START, TZ, epochs, load_academic, load_ema, load_surveys, read_csv

NUMERIC_COLUMNS = ["sleep_hours_inferred", "bedtime_hour", "active_minutes", "walk_minutes",
                   "run_minutes", "conversation_count", "conversation_minutes", "calls", "sms",
                   "ema_stress_mean", "ema_mood_valence", "ema_sleep_hours"]


def merge_intervals(intervals, gap=0):
    out = []
    for start, end in sorted(intervals):
        if end <= start:
            continue
        if out and start <= out[-1][1] + gap:
            out[-1] = (out[-1][0], max(out[-1][1], end))
        else:
            out.append((start, end))
    return out


def intersect_intervals(left, right):
    out, i, j = [], 0, 0
    while i < len(left) and j < len(right):
        start, end = max(left[i][0], right[j][0]), min(left[i][1], right[j][1])
        if end > start:
            out.append((start, end))
        if left[i][1] < right[j][1]:
            i += 1
        else:
            j += 1
    return out


def intervals(data_dir, kind, uid):
    frame = read_csv(Path(data_dir) / "sensing" / kind / f"{kind}_{uid}.csv")
    if frame.empty:
        return []
    start = pd.to_numeric(frame.iloc[:, 0], errors="coerce")
    end = pd.to_numeric(frame.iloc[:, 1], errors="coerce")
    return merge_intervals([(float(a), float(b)) for a, b in zip(start, end)
                            if pd.notna(a) and pd.notna(b) and b > a])


def daily_features(data_dir, uid, ema, academic):
    activity = read_csv(Path(data_dir) / "sensing/activity" / f"activity_{uid}.csv")
    if len(activity):
        activity["time"] = epochs(activity.iloc[:, 0])
        activity["state"] = pd.to_numeric(activity.iloc[:, 1], errors="coerce")
        activity = activity.dropna(subset=["time"])
    dark = intervals(data_dir, "dark", uid)
    locked = merge_intervals(intervals(data_dir, "phonelock", uid) +
                             intervals(data_dir, "phonecharge", uid))
    # Intersect before bridging so a long charging period alone is never called sleep.
    sleep = merge_intervals(intersect_intervals(dark, locked), gap=20 * 60)
    conversation = intervals(data_dir, "conversation", uid)
    dates = [TERM_START, pd.Timestamp("2013-06-15")]
    if len(activity):
        dates.append(activity["time"].max().tz_localize(None).normalize())
    if len(ema):
        dates.append(ema["time"].max().tz_localize(None).normalize())
    days = pd.date_range(TERM_START, max(dates), freq="D")
    daily = pd.DataFrame(index=days)
    daily.index.name = "date"
    for col in NUMERIC_COLUMNS:
        daily[col] = np.nan
    daily["bedtime"] = pd.Series(index=days, dtype="str")
    daily["wake_time"] = pd.Series(index=days, dtype="str")
    for col in ("has_sleep", "has_activity", "has_conversation"):
        daily[col] = False

    if len(activity):
        valid = activity[activity["state"].isin([0, 1, 2])].copy()
        valid["bin"] = valid["time"].dt.floor("10min")
        # Each observed ten-minute bin is weighted once; repeated samples do not inflate time.
        binned = valid.groupby("bin")["state"].agg(
            walk=lambda s: (s == 1).mean(), run=lambda s: (s == 2).mean())
        binned["date"] = binned.index.tz_localize(None).normalize()
        for date, frame in binned.groupby("date"):
            if date in daily.index and len(frame) >= 72:
                daily.loc[date, ["walk_minutes", "run_minutes"]] = frame[["walk", "run"]].sum().values * 10
                daily.loc[date, "active_minutes"] = daily.loc[date, "walk_minutes"] + daily.loc[date, "run_minutes"]
                daily.loc[date, "has_activity"] = True

    for date in days:
        midnight = date.tz_localize(TZ)
        start = (date - pd.Timedelta(days=1) + pd.Timedelta(hours=18)).tz_localize(TZ).timestamp()
        end = (date + pd.Timedelta(hours=12)).tz_localize(TZ).timestamp()
        candidates = [(max(a, start), min(b, end)) for a, b in sleep
                      if a < end and b > start and a < midnight.timestamp() + 7 * 3600
                      and b > midnight.timestamp()]
        candidates = [(a, b) for a, b in candidates if 1.5 <= (b-a) / 3600 <= 14]
        if candidates:
            a, b = max(candidates, key=lambda pair: pair[1] - pair[0])
            bed = pd.Timestamp(a, unit="s", tz=TZ)
            wake = pd.Timestamp(b, unit="s", tz=TZ)
            daily.loc[date, ["sleep_hours_inferred", "bedtime_hour"]] = [(b-a)/3600, bed.hour + bed.minute/60]
            daily.loc[date, ["bedtime", "wake_time"]] = [bed.strftime("%H:%M"), wake.strftime("%H:%M")]
            daily.loc[date, "has_sleep"] = True
        day_end = (date + pd.Timedelta(days=1)).tz_localize(TZ).timestamp()
        segments = [(max(a, midnight.timestamp()), min(b, day_end)) for a, b in conversation
                    if a < day_end and b > midnight.timestamp()]
        # A day with no detections is zero only if other sensing establishes coverage.
        if segments or daily.loc[date, "has_activity"]:
            daily.loc[date, ["conversation_count", "conversation_minutes"]] = [
                len(segments), sum(b-a for a, b in segments)/60]
            daily.loc[date, "has_conversation"] = True

    for kind, event_col in (("call_log", "CALLS_date"), ("sms", "MESSAGES_date")):
        frame = read_csv(Path(data_dir) / kind / f"{kind}_{uid}.csv")
        if frame.empty or event_col not in frame:
            continue
        event = epochs(frame[event_col], unit="ms")
        observed = epochs(frame["timestamp"])
        # Phone logs can contain older events first uploaded later. Use availability time.
        frame["available"] = pd.concat([event, observed], axis=1).max(axis=1)
        frame = frame.sort_values("available").drop_duplicates(subset=[event_col])
        counts = frame.groupby(frame["available"].dt.tz_localize(None).dt.normalize()).size()
        col = "calls" if kind == "call_log" else "sms"
        daily.loc[daily["has_activity"], col] = 0
        overlap = daily.index.intersection(counts.index)
        daily.loc[overlap, col] = counts.loc[overlap]
    if len(ema):
        dated = ema.assign(date=ema["time"].dt.tz_localize(None).dt.normalize())
        for source, target in (("stress", "ema_stress_mean"), ("mood_valence", "ema_mood_valence"),
                               ("sleep_hours", "ema_sleep_hours")):
            values = dated.groupby("date")[source].mean()
            overlap = daily.index.intersection(values.index)
            daily.loc[overlap, target] = values.loc[overlap]
    dl = academic.get("deadlines", {})
    daily["deadlines_today"] = [dl.get(d.strftime("%Y-%m-%d"), 0) for d in days]
    daily["deadlines_next_3d"] = [sum(dl.get((d + pd.Timedelta(days=k)).strftime("%Y-%m-%d"), 0)
                                           for k in range(1, 4)) for d in days]
    daily["term_week"] = ((daily.index - TERM_START).days // 7) + 1
    return daily.reset_index()


def preprocess(data_dir="data", out_dir="cache/features", verbose=False):
    base, target = Path(data_dir), Path(out_dir)
    files = sorted((base / "sensing/activity").glob("activity_u*.csv"))
    if not files:
        raise FileNotFoundError(f"No StudentLife activity files under {base / 'sensing/activity'}")
    target.mkdir(parents=True, exist_ok=True)
    academic, surveys = load_academic(base), load_surveys(base)
    uids = [p.stem.removeprefix("activity_") for p in files]
    for uid in uids:
        ema = load_ema(base, uid)
        daily_features(base, uid, ema, academic.get(uid, {})).to_parquet(target / f"daily_{uid}.parquet", index=False)
        ema.to_parquet(target / f"ema_{uid}.parquet", index=False)
        if verbose:
            print(f"Preprocessed {uid}")
    (target / "surveys.json").write_text(json.dumps(surveys, indent=2), encoding="utf-8")
    (target / "academic.json").write_text(json.dumps(academic, indent=2), encoding="utf-8")
    return {"uids": uids, "out_dir": str(target)}
