"""Sensing / EMA tools. Each `make_*` returns a closure bound to a time-bounded View."""

from __future__ import annotations

import pandas as pd

from ..data.loaders import STRESS_LABELS
from ._common import baseline, clamp_days, masked, mean_or_none, no_data, rnd

PHASES = [(3, "early term"), (6, "midterms"), (9, "late term"), (99, "finals")]


def _phase(week: int) -> str:
    if week < 1:
        return "before term"
    return next(p for w, p in PHASES if week <= w)


def _time_of_day(h: int) -> str:
    return ("night" if h < 6 else "morning" if h < 12 else "afternoon" if h < 17
            else "evening" if h < 22 else "night")


def _class_now(view) -> str | None:
    t = view.decision_time
    hm = t.strftime("%H:%M")
    for c in view.academic.get("classes", []):
        for p in c["periods"]:
            if p["day"] == t.isoweekday() and p["start"] <= hm <= p["end"]:
                return c["course"]
    return None


def make_time_context(view):
    def get_time_context() -> dict:
        """Get the current decision-time context: date, weekday, local time, part of day,
        term week, term phase (early term / midterms / late term / finals) and whether a
        class is scheduled right now.

        Returns:
            dict: Time context with a short summary.
        """
        t = view.decision_time
        wk = view.term_week
        out = {"source": "context.time", "date": t.strftime("%Y-%m-%d"), "weekday": t.day_name(),
               "local_time": t.strftime("%H:%M"), "time_of_day": _time_of_day(t.hour),
               "term_week": wk, "term_phase": _phase(wk)}
        if not view.is_masked("academic"):
            out["class_now"] = _class_now(view)
        out["summary"] = (f"{t.day_name()} {t.strftime('%H:%M')} ({out['time_of_day']}), "
                          f"term week {wk} ({out['term_phase']})"
                          + (f", in class {out['class_now']}" if out.get("class_now") else ""))
        return out
    return get_time_context


def make_sleep_summary(view):
    def get_sleep_summary(days: int = 3) -> dict:
        """Summarize the student's recent sleep: phone-inferred sleep duration, bedtime and
        wake time (from screen-off/lock/charging), self-reported EMA sleep hours and quality,
        and the difference from the student's own baseline.

        Args:
            days: Number of past complete days (nights) to summarize, 1-30.

        Returns:
            dict: Sleep summary with a short human-readable summary string.
        """
        src = "sensing.sleep"
        if view.is_masked("sleep"):
            return masked(src)
        days = clamp_days(days)
        rows = view.last_days(days)
        inf = rows["sleep_hours_inferred"].dropna()
        out: dict = {"source": src, "window_days": days, "nights_with_data": int(len(inf))}
        if len(inf):
            out["inferred_hours_mean"] = rnd(inf.mean())
            out["inferred_hours_min"] = rnd(inf.min())
            out["latest_bedtime"] = rows["bedtime"].dropna().iloc[-1]
            out["latest_wake_time"] = rows["wake_time"].dropna().iloc[-1]
        if view.last_night:
            out["last_night_hours"] = rnd(view.last_night["sleep_hours_inferred"])
            out["last_night_bed_wake"] = f"{view.last_night['bedtime']}-{view.last_night['wake_time']}"
        bm, bs, bn = baseline(view, "sleep_hours_inferred", days)
        if bm is not None and len(inf):
            out["baseline_hours"] = rnd(bm)
            out["delta_vs_baseline_h"] = rnd(inf.mean() - bm)
        if not view.is_masked("ema"):
            e = view.ema_since(24 * days, ("sleep",))
            if len(e):
                out["self_report_hours_mean"] = rnd(e["sleep_hours"].mean())
                out["self_report_quality_mean_1to4"] = rnd(e["sleep_quality"].mean())
                out["self_reports"] = int(len(e))
        if len(out) <= 3:
            return no_data(src, f" in the last {days} days")
        parts = []
        if "inferred_hours_mean" in out:
            parts.append(f"inferred {out['inferred_hours_mean']}h/night over {len(inf)} nights")
        if "last_night_hours" in out:
            parts.append(f"last night {out['last_night_hours']}h")
        if "delta_vs_baseline_h" in out:
            parts.append(f"{out['delta_vs_baseline_h']:+}h vs usual {out['baseline_hours']}h")
        if "self_report_hours_mean" in out:
            parts.append(f"self-report {out['self_report_hours_mean']}h, quality "
                         f"{out['self_report_quality_mean_1to4']}/4")
        out["summary"] = "Sleep: " + "; ".join(parts)
        return out
    return get_sleep_summary


def make_activity_summary(view):
    def get_activity_summary(days: int = 3) -> dict:
        """Summarize recent physical activity from the phone's activity recognition
        (estimated walking/running minutes per day) and self-reported exercise, compared to
        the student's own baseline.

        Args:
            days: Number of past complete days to summarize, 1-30.

        Returns:
            dict: Activity summary with a short human-readable summary string.
        """
        src = "sensing.activity"
        if view.is_masked("activity"):
            return masked(src)
        days = clamp_days(days)
        rows = view.last_days(days)
        rows = rows[rows["has_activity"]]
        out: dict = {"source": src, "window_days": days, "days_with_data": int(len(rows))}
        if len(rows):
            out["active_min_per_day"] = rnd(rows["active_minutes"].mean(), 0)
            out["walk_min_per_day"] = rnd(rows["walk_minutes"].mean(), 0)
            out["run_min_per_day"] = rnd(rows["run_minutes"].mean(), 0)
            bm, _, _ = baseline(view, "active_minutes", days)
            if bm is not None:
                out["baseline_active_min"] = rnd(bm, 0)
                out["pct_vs_baseline"] = rnd(100 * (rows["active_minutes"].mean() - bm) / max(bm, 1), 0)
        if not view.is_masked("ema"):
            e = view.ema_since(24 * days, ("exercise",))
            if len(e):
                out["self_report_exercised_days"] = int(e["exercised"].sum())
                out["self_reports"] = int(len(e))
        if len(out) <= 3:
            return no_data(src, f" in the last {days} days")
        parts = []
        if "active_min_per_day" in out:
            parts.append(f"~{out['active_min_per_day']} active min/day (walk {out['walk_min_per_day']}, "
                         f"run {out['run_min_per_day']}) over {len(rows)} days")
        if "pct_vs_baseline" in out:
            parts.append(f"{out['pct_vs_baseline']:+}% vs usual {out['baseline_active_min']} min")
        if "self_reports" in out:
            parts.append(f"self-reported vigorous exercise {out['self_report_exercised_days']}/"
                         f"{out['self_reports']} reports")
        out["summary"] = "Activity: " + "; ".join(parts)
        return out
    return get_activity_summary


def make_social_summary(view):
    def get_social_summary(days: int = 3) -> dict:
        """Summarize recent social interaction: detected face-to-face conversations
        (count and minutes per day), phone calls and SMS per day, and self-reported number
        of social contacts, compared to the student's own baseline.

        Args:
            days: Number of past complete days to summarize, 1-30.

        Returns:
            dict: Social summary with a short human-readable summary string.
        """
        src = "sensing.social"
        if view.is_masked("social"):
            return masked(src)
        days = clamp_days(days)
        rows = view.last_days(days)
        out: dict = {"source": src, "window_days": days}
        if view.is_masked("conversation"):
            out["conversation"] = "missing: masked (synthetic)"
        else:
            cr = rows[rows["has_conversation"]]
            if len(cr):
                out["conversations_per_day"] = rnd(cr["conversation_count"].mean())
                out["conversation_min_per_day"] = rnd(cr["conversation_minutes"].mean(), 0)
                bm, _, _ = baseline(view, "conversation_minutes", days)
                if bm is not None:
                    out["baseline_conversation_min"] = rnd(bm, 0)
            else:
                out["conversation"] = "missing: no data"
        pr = rows[rows["has_activity"]]
        if len(pr):
            for k, col in (("calls_per_day", "calls"), ("sms_per_day", "sms")):
                v = rnd(pr[col].mean())
                if v is not None:
                    out[k] = v
        if not view.is_masked("ema"):
            e = view.ema_since(24 * days, ("social",))
            if len(e):
                cat = rnd(e["social_contacts_cat"].mean(), 0)
                out["self_report_contacts"] = {1: "0-4", 2: "5-9", 3: "10-19", 4: "20-49", 5: "50-99",
                                               6: "100+"}.get(cat, None)
        if not any(k in out for k in ("conversations_per_day", "calls_per_day", "sms_per_day",
                                      "self_report_contacts")):
            r = no_data(src, f" in the last {days} days")
            if "conversation" in out:
                r["conversation"] = out["conversation"]
            return r
        parts = []
        if "conversation_min_per_day" in out:
            s = f"{out['conversations_per_day']} conversations/day ({out['conversation_min_per_day']} min)"
            if "baseline_conversation_min" in out:
                s += f" vs usual {out['baseline_conversation_min']} min"
            parts.append(s)
        elif "conversation" in out:
            parts.append(f"conversation {out['conversation']}")
        if "calls_per_day" in out:
            parts.append(f"{out['calls_per_day']} calls/day")
        if "sms_per_day" in out:
            parts.append(f"{out['sms_per_day']} SMS/day")
        if out.get("self_report_contacts"):
            parts.append(f"self-reported {out['self_report_contacts']} contacts/day")
        out["summary"] = "Social: " + "; ".join(parts)
        return out
    return get_social_summary


def make_stress_mood_history(view):
    def get_stress_mood_history(days: int = 3) -> dict:
        """Summarize recent self-reported stress (EMA, 1=feeling great .. 5=stressed out),
        mood (happy minus sad), photographic affect meter (PAM valence/arousal, 1-4), the most
        recent free-text comment, and pre-term survey scores (PSS, PHQ-9, loneliness).

        Args:
            days: Number of past days of EMA responses to summarize, 1-30.

        Returns:
            dict: Stress and mood summary with a short human-readable summary string.
        """
        src = "ema.stress"
        if view.is_masked("ema", "stress"):
            return masked(src)
        days = clamp_days(days)
        e = view.ema_since(24 * days)
        out: dict = {"source": src, "window_days": days}
        st = e[e["type"] == "stress"]
        if len(st):
            last = st.iloc[-1]
            out["stress_n"] = int(len(st))
            out["stress_mean_1to5"] = rnd(st["stress"].mean())
            out["stress_max"] = int(st["stress"].max())
            out["last_stress"] = int(last["stress"])
            out["last_stress_label"] = STRESS_LABELS[int(last["stress"])]
            out["last_stress_hours_ago"] = rnd((view.decision_time - last["time"]).total_seconds() / 3600)
            bm, _, _ = baseline(view, "ema_stress_mean", days)
            if bm is not None:
                out["baseline_stress"] = rnd(bm)
        mood = mean_or_none(e.loc[e["type"] == "mood", "mood_valence"])
        if mood is not None:
            out["mood_valence_mean"] = rnd(mood)
        pam = e[e["type"] == "pam"]
        if len(pam):
            out["pam_valence_mean"] = rnd(pam["pam_valence"].mean())
            out["pam_arousal_mean"] = rnd(pam["pam_arousal"].mean())
        com = view.ema[(view.ema["type"] == "comment")
                       & (view.ema["time"] >= view.decision_time - pd.Timedelta(days=14))]
        if len(com):
            c = com.iloc[-1]
            out["last_comment"] = str(c["comment"])[:200]
            out["last_comment_days_ago"] = rnd((view.decision_time - c["time"]).total_seconds() / 86400)
        sv = {k: v for k, v in view.surveys.items()
              if k in ("pss_total", "phq9_total", "loneliness_total", "phq9_item9_selfharm")}
        if len(out) <= 2:
            r = no_data(src, f" in the last {days} days")
            if sv:
                r["pre_term_surveys"] = sv
            return r
        if sv:
            out["pre_term_surveys"] = sv
        parts = []
        if "stress_n" in out:
            parts.append(f"stress mean {out['stress_mean_1to5']}/5 over {out['stress_n']} reports, last "
                         f"'{out['last_stress_label']}' {out['last_stress_hours_ago']}h ago")
            if "baseline_stress" in out:
                parts.append(f"usual {out['baseline_stress']}/5")
        if "mood_valence_mean" in out:
            parts.append(f"mood valence {out['mood_valence_mean']}")
        if "pam_valence_mean" in out:
            parts.append(f"PAM valence {out['pam_valence_mean']}/4 arousal {out['pam_arousal_mean']}/4")
        if "last_comment" in out:
            parts.append(f"last comment ({out['last_comment_days_ago']}d ago): \"{out['last_comment'][:80]}\"")
        out["summary"] = "Stress/mood: " + ("; ".join(parts) if parts else "no recent EMA")
        return out
    return get_stress_mood_history


BASELINE_FEATURES = {
    "sleep_hours": ("sleep_hours_inferred", "sleep"),
    "bedtime": ("bedtime_hour", "sleep"),
    "active_minutes": ("active_minutes", "activity"),
    "walk_minutes": ("walk_minutes", "activity"),
    "conversation_minutes": ("conversation_minutes", "conversation"),
    "conversation_count": ("conversation_count", "conversation"),
    "calls": ("calls", "social"),
    "sms": ("sms", "social"),
    "stress": ("ema_stress_mean", "stress"),
    "mood": ("ema_mood_valence", "stress"),
    "self_report_sleep": ("ema_sleep_hours", "ema"),
}


def make_compare_to_baseline(view):
    def compare_to_baseline(feature: str, days: int = 3) -> dict:
        """Compare the student's recent mean of a feature to their own history (z-score of
        the recent window against all earlier complete days up to the decision time).

        Args:
            feature: One of sleep_hours, bedtime, active_minutes, walk_minutes,
                conversation_minutes, conversation_count, calls, sms, stress, mood,
                self_report_sleep.
            days: Length of the recent window in complete days, 1-30.

        Returns:
            dict: Recent mean, baseline mean/std, z-score and a short summary.
        """
        src = f"baseline.{feature}"
        if feature not in BASELINE_FEATURES:
            return {"source": "baseline", "status": "error",
                    "summary": f"unknown feature '{feature}'; valid: {sorted(BASELINE_FEATURES)}"}
        col, mod = BASELINE_FEATURES[feature]
        if view.is_masked(mod) or (mod in ("stress", "ema") and view.is_masked("ema")) or \
                (mod == "conversation" and view.is_masked("social")):
            return masked(src)
        days = clamp_days(days)
        recent = mean_or_none(view.last_days(days)[col])
        bm, bs, bn = baseline(view, col, days)
        if recent is None or bm is None:
            return no_data(src, f" (recent n/a or <3 baseline days)")
        z = (recent - bm) / bs if bs and bs > 1e-9 else 0.0
        level = "much lower" if z < -1.5 else "lower" if z < -0.5 else "much higher" if z > 1.5 \
            else "higher" if z > 0.5 else "typical"
        return {"source": src, "feature": feature, "window_days": days, "recent_mean": rnd(recent, 2),
                "baseline_mean": rnd(bm, 2), "baseline_std": rnd(bs, 2), "baseline_days": bn,
                "z": rnd(z, 2), "level": level,
                "summary": f"{feature}: recent {rnd(recent, 2)} vs usual {rnd(bm, 2)} "
                           f"(z={rnd(z, 2)}, {level})"}
    return compare_to_baseline
