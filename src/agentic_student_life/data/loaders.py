"""Read the supplied StudentLife CSV/JSON schemas without exposing raw identifiers."""
from __future__ import annotations

import csv
import json
from pathlib import Path

import numpy as np
import pandas as pd

TZ = "America/New_York"
TERM_START = pd.Timestamp("2013-03-25")
STRESS_MAP = {1: 3, 2: 4, 3: 5, 4: 2, 5: 1}
STRESS_LABELS = {1: "feeling great", 2: "feeling good", 3: "a little stressed",
                 4: "definitely stressed", 5: "stressed out"}
EMA_COLUMNS = ["time", "type", "stress", "sleep_hours", "sleep_quality", "exercised",
               "social_contacts_cat", "mood_valence", "pam_valence", "pam_arousal", "comment"]


def local_time(value):
    t = pd.Timestamp(value)
    return t.tz_localize(TZ) if t.tzinfo is None else t.tz_convert(TZ)


def read_csv(path):
    if not Path(path).exists():
        return pd.DataFrame()
    frame = pd.read_csv(path, low_memory=False)
    frame.columns = frame.columns.str.strip()
    return frame


def epochs(values, unit="s"):
    return pd.to_datetime(pd.to_numeric(values, errors="coerce"), unit=unit,
                          utc=True, errors="coerce").dt.tz_convert(TZ)


def load_ema(data_dir, uid):
    records = []
    names = {"Stress": "stress", "Sleep": "sleep", "Exercise": "exercise",
             "Social": "social", "Mood": "mood", "PAM": "pam", "Comment": "comment"}
    for folder, kind in names.items():
        path = Path(data_dir) / "EMA/response" / folder / f"{folder}_{uid}.json"
        if not path.exists():
            continue
        for item in json.loads(path.read_text(encoding="utf-8")):
            if not item.get("resp_time"):
                continue
            row = {"time": pd.to_datetime(item["resp_time"], unit="s", utc=True).tz_convert(TZ),
                   "type": kind}
            def number(key):
                try:
                    return float(item[key])
                except (KeyError, ValueError, TypeError):
                    return np.nan
            if kind == "stress":
                row["stress"] = STRESS_MAP.get(number("level"), np.nan)
                if pd.isna(row["stress"]):
                    continue
            elif kind == "sleep":
                row.update(sleep_hours=number("hour"), sleep_quality=number("rate"))
            elif kind == "exercise":
                row["exercised"] = float(number("have") == 1) if number("have") in (1, 2) else np.nan
            elif kind == "social":
                row["social_contacts_cat"] = number("number")
            elif kind == "mood":
                row["mood_valence"] = number("happy") - number("sad")
            elif kind == "pam":
                idx = number("picture_idx")
                if 1 <= idx <= 16:
                    row.update(pam_valence=(int(idx) - 1) % 4 + 1, pam_arousal=4 - (int(idx) - 1) // 4)
            elif kind == "comment":
                row["comment"] = str(item.get("comment", ""))
            records.append(row)
    frame = pd.DataFrame(records, columns=EMA_COLUMNS)
    frame["time"] = pd.to_datetime(frame["time"], utc=True).dt.tz_convert(TZ)
    for col in EMA_COLUMNS[2:-1]:
        frame[col] = pd.to_numeric(frame[col], errors="coerce")
    return frame.sort_values("time").reset_index(drop=True)


def load_academic(data_dir):
    base = Path(data_dir) / "education"
    info = json.loads((base / "class_info.json").read_text(encoding="utf-8"))
    result = {}
    with (base / "class.csv").open(newline="", encoding="utf-8-sig") as stream:
        for row in csv.reader(stream):
            if row and row[0].startswith("u"):
                result[row[0]] = {"classes": [{"course": c, **info.get(c, {})}
                                               for c in row[1:] if c], "deadlines": {}}
    with (base / "deadlines.csv").open(newline="", encoding="utf-8-sig") as stream:
        rows = csv.reader(stream)
        header = next(rows)
        for row in rows:
            if not row:
                continue
            entry = result.setdefault(row[0], {"classes": [], "deadlines": {}})
            entry["deadlines"] = {date: int(float(v)) for date, v in zip(header[1:], row[1:])
                                  if v.strip()}
    return result


def load_surveys(data_dir):
    result = {}
    definitions = [
        ("PerceivedStressScale.csv", ["never", "almost never", "sometime", "fairly often", "very often"],
         {4, 5, 7, 8}, "pss_total", 0),
        ("PHQ-9.csv", ["not at all", "several days", "more than half the days", "nearly every day"],
         set(), "phq9_total", 0),
        ("LonelinessScale.csv", ["never", "rarely", "sometimes", "often"],
         {1, 4, 5, 6, 9, 10, 15, 16, 19, 20}, "loneliness_total", 1),
        ("BigFive.csv", ["disagree strongly", "disagree a little", "neither agree nor disagree",
                         "agree a little", "agree strongly"], set(), "bfi", 1),
    ]
    traits = {
        "extraversion": ([1, 6, 11, 16, 21, 26, 31, 36], {6, 21, 31}),
        "agreeableness": ([2, 7, 12, 17, 22, 27, 32, 37, 42], {2, 12, 27, 37}),
        "conscientiousness": ([3, 8, 13, 18, 23, 28, 33, 38, 43], {8, 18, 23, 43}),
        "neuroticism": ([4, 9, 14, 19, 24, 29, 34, 39], {9, 24, 34}),
        "openness": ([5, 10, 15, 20, 25, 30, 35, 40, 41, 44], {35, 41}),
    }
    for filename, labels, reverse, key, offset in definitions:
        frame = read_csv(Path(data_dir) / "survey" / filename)
        if frame.empty:
            continue
        count = 9 if key == "phq9_total" else len(frame.columns) - 2
        for _, row in frame[frame["type"].str.lower() == "pre"].iterrows():
            values = []
            for v in row.iloc[2:2 + count]:
                label = str(v).strip().lower()
                values.append(labels.index(label) + offset if label in labels else np.nan)
            out = result.setdefault(row["uid"], {})
            if key == "bfi":
                for trait, (items, rev) in traits.items():
                    scores = [6 - values[i-1] if i in rev else values[i-1] for i in items]
                    if not any(pd.isna(x) for x in scores):
                        out[f"bfi_{trait}"] = round(float(np.mean(scores)), 2)
            elif not any(pd.isna(x) for x in values):
                high = len(labels) - 1 + offset
                out[key] = float(sum(high + offset - v if i in reverse else v
                                     for i, v in enumerate(values, 1)))
                if key == "phq9_total":
                    out["phq9_item9_selfharm"] = int(values[8])
    return result
