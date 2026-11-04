"""Leak-free tools bound to a time-bounded View.

    from agentic_student_life.data.store import DataStore
    from agentic_student_life.tools import make_tools, evidence_summary
    view = DataStore().get_view("u59", "2013-04-20 21:00", mask=["sleep"])
    tools = make_tools(view)          # list of plain callables for aisuite tools=[...]
    ev = evidence_summary(view)       # dict of default-window tool outputs
"""

from __future__ import annotations

from typing import Callable

from .academic import make_academic_load
from .resources import search_campus_resources
from .sensing import (BASELINE_FEATURES, make_activity_summary, make_compare_to_baseline,
                      make_sleep_summary, make_social_summary, make_stress_mood_history,
                      make_time_context)

__all__ = ["make_tools", "evidence_summary", "search_campus_resources", "BASELINE_FEATURES"]


def make_tools(view) -> list[Callable]:
    """Return the tool callables (closures over `view`; they cannot see data after t)."""
    return [
        make_time_context(view),
        make_sleep_summary(view),
        make_activity_summary(view),
        make_social_summary(view),
        make_stress_mood_history(view),
        make_academic_load(view),
        make_compare_to_baseline(view),
        search_campus_resources,
    ]


def tool_map(view) -> dict[str, Callable]:
    return {f.__name__: f for f in make_tools(view)}


def evidence_summary(view) -> dict:
    """Call all summary tools with default windows (used by no-tools baseline and judge)."""
    t = tool_map(view)
    return {
        "time_context": t["get_time_context"](),
        "sleep_3d": t["get_sleep_summary"](3),
        "activity_3d": t["get_activity_summary"](3),
        "social_3d": t["get_social_summary"](3),
        "stress_mood_3d": t["get_stress_mood_history"](3),
        "stress_mood_7d": t["get_stress_mood_history"](7),
        "academic_3d": t["get_academic_load"](3),
        "baseline_sleep_7d": t["compare_to_baseline"]("sleep_hours", 7),
        "baseline_activity_7d": t["compare_to_baseline"]("active_minutes", 7),
        "baseline_conversation_7d": t["compare_to_baseline"]("conversation_minutes", 7),
    }

