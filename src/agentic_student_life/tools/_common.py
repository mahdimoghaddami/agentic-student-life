"""Shared helpers for the leak-free tools."""

from __future__ import annotations

import math

import numpy as np
import pandas as pd

from ..data.store import MASKED, NO_DATA


def rnd(x, n: int = 1):
    """Round to n digits; NaN/None -> None (JSON friendly)."""
    if x is None:
        return None
    try:
        x = float(x)
    except (TypeError, ValueError):
        return None
    if math.isnan(x) or math.isinf(x):
        return None
    return round(x, n) if n else int(round(x))


def masked(source: str) -> dict:
    return {"source": source, **MASKED, "summary": f"{source}: masked (synthetic missing data)"}


def no_data(source: str, extra: str = "") -> dict:
    return {"source": source, **NO_DATA, "summary": f"{source}: no data{extra}"}


def baseline(view, col: str, days: int) -> tuple[float | None, float | None, int]:
    """Mean/std of `col` over the student's complete days BEFORE the recent window."""
    start = pd.Timestamp(view.decision_date) - pd.Timedelta(days=max(1, int(days)))
    hist = view.daily.loc[view.daily["date"] < start, col].dropna() if col in view.daily else pd.Series([], dtype=float)
    if len(hist) < 3:
        return None, None, len(hist)
    return float(hist.mean()), float(hist.std(ddof=1)) if len(hist) > 1 else None, len(hist)


def mean_or_none(s: pd.Series):
    s = pd.to_numeric(s, errors="coerce").dropna()
    return float(s.mean()) if len(s) else None


def clamp_days(days, lo: int = 1, hi: int = 30) -> int:
    try:
        d = int(days)
    except (TypeError, ValueError):
        d = 3
    return int(np.clip(d, lo, hi))

