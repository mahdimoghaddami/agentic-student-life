"""Cached data access; only explicitly bounded copies reach agent tools."""
from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path

import pandas as pd

from .loaders import TERM_START, local_time

MASKED = {"status": "missing", "reason": "masked (synthetic)"}
NO_DATA = {"status": "missing", "reason": "no data"}


@dataclass(frozen=True)
class View:
    uid: str
    decision_time: pd.Timestamp
    daily: pd.DataFrame
    ema: pd.DataFrame
    surveys: dict
    academic: dict
    mask: frozenset[str]
    last_night: dict | None = None

    @property
    def decision_date(self):
        return self.decision_time.date()

    @property
    def term_week(self):
        return (pd.Timestamp(self.decision_date) - TERM_START).days // 7 + 1

    def is_masked(self, *modalities):
        return any(m in self.mask for m in modalities)

    def last_days(self, days):
        start = pd.Timestamp(self.decision_date) - pd.Timedelta(days=max(1, int(days)))
        return self.daily[self.daily["date"] >= start].copy()

    def ema_since(self, hours, types=None):
        frame = self.ema[self.ema["time"] > self.decision_time - pd.Timedelta(hours=hours)]
        if types:
            frame = frame[frame["type"].isin(types)]
        return frame.copy()


class DataStore:
    def __init__(self, cache_dir="cache/features"):
        self.cache_dir = Path(cache_dir)
        self._daily, self._ema = {}, {}
        try:
            self.surveys = json.loads((self.cache_dir / "surveys.json").read_text(encoding="utf-8"))
            self.academic = json.loads((self.cache_dir / "academic.json").read_text(encoding="utf-8"))
        except FileNotFoundError as exc:
            raise FileNotFoundError(f"Missing features in {self.cache_dir}; run 'asl preprocess' first.") from exc

    def uids(self):
        return sorted(p.stem.removeprefix("daily_") for p in self.cache_dir.glob("daily_u*.parquet"))

    def daily(self, uid):
        if uid not in self._daily:
            self._daily[uid] = pd.read_parquet(self.cache_dir / f"daily_{uid}.parquet")
        return self._daily[uid]

    def ema(self, uid):
        if uid not in self._ema:
            self._ema[uid] = pd.read_parquet(self.cache_dir / f"ema_{uid}.parquet")
        return self._ema[uid]

    def get_view(self, uid, decision_time, mask=None):
        t = local_time(decision_time)
        date = pd.Timestamp(t.date())
        daily, ema = self.daily(uid), self.ema(uid)
        last_night = None
        # A sleep inference's fixed overnight window closes at noon on the wake date.
        if t.hour >= 12:
            night = daily[(daily["date"] == date) & daily["has_sleep"]]
            if len(night):
                last_night = night.iloc[-1][["sleep_hours_inferred", "bedtime", "wake_time"]].to_dict()
        return View(uid, t, daily[daily["date"] < date].copy(),
                    ema[ema["time"] <= t].copy(), dict(self.surveys.get(uid, {})),
                    self.academic.get(uid, {}), frozenset(mask or []), last_night)
