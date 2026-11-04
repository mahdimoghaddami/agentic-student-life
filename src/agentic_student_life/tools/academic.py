"""Academic-load tool (deadlines.csv + class schedule; syllabus data known in advance)."""

from __future__ import annotations

import pandas as pd

from ._common import clamp_days, masked, no_data


def make_academic_load(view):
    def get_academic_load(days_ahead: int = 3) -> dict:
        """Get the student's academic load: number of deadlines today and in each of the next
        days (from course syllabi), and today's scheduled classes.

        Args:
            days_ahead: How many upcoming days of deadlines to include, 1-14.

        Returns:
            dict: Deadline counts (by days from now) and today's classes, with a summary.
        """
        src = "education.deadlines"
        if view.is_masked("academic"):
            return masked(src)
        acad = view.academic
        if not acad or ("deadlines" not in acad and "classes" not in acad):
            return no_data(src)
        days_ahead = clamp_days(days_ahead, 1, 14)
        d0 = pd.Timestamp(view.decision_date)
        dl = acad.get("deadlines", {})
        today = int(dl.get(d0.strftime("%Y-%m-%d"), 0))
        ahead = {f"in_{k}d": int(dl.get((d0 + pd.Timedelta(days=k)).strftime("%Y-%m-%d"), 0))
                 for k in range(1, days_ahead + 1)}
        hm = view.decision_time.strftime("%H:%M")
        wd = view.decision_time.isoweekday()
        classes = sorted((p["start"], p["end"], c["course"]) for c in acad.get("classes", [])
                         for p in c["periods"] if p["day"] == wd)
        out = {"source": src, "deadlines_today": today, "deadlines_ahead": ahead,
               "deadlines_next_window": sum(ahead.values()),
               "classes_today": [f"{c} {s}-{e}" for s, e, c in classes],
               "classes_remaining_today": sum(1 for s, _, _ in classes if s > hm),
               "n_courses": len(acad.get("classes", []))}
        out["summary"] = (f"Academic: {today} deadline(s) today, {out['deadlines_next_window']} in next "
                          f"{days_ahead} days; {len(classes)} class(es) today "
                          f"({out['classes_remaining_today']} remaining)")
        return out
    return get_academic_load

