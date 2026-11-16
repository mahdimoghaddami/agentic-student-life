"""Context Analyst agent (executes leak-free data tools to gather evidence)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

from ..config import RunConfig
from ..llm import CallTracker, LLMClient
from .schemas import AnalystOutput

PROMPT_PATH = Path("prompts/analyst.md")


def load_analyst_prompt() -> str:
    if PROMPT_PATH.exists():
        return PROMPT_PATH.read_text(encoding="utf-8")
    return "You are the Context Analyst in a multi-agent student stress-coaching system."


def run_analyst(
    *,
    llm: LLMClient,
    cfg: RunConfig,
    tracker: CallTracker,
    case: dict[str, Any],
    plan_steps: list[str],
    hypotheses: list[str],
    tools: list[Callable],
    precomputed_summary: dict[str, Any] | None = None,
) -> AnalystOutput:
    """Run the Context Analyst using tools (or precomputed summary if tools are disabled)."""
    sys_prompt = load_analyst_prompt()
    if plan_steps:
        plan_section = (
            f"## Planner Hypotheses\n{json.dumps(hypotheses, indent=2)}\n\n"
            f"## Requested Plan Steps to Execute\n{json.dumps(plan_steps, indent=2)}"
        )
    else:
        plan_section = (
            "## Autonomous Evidence Collection (No Planner Mode)\n"
            "Call tools to inspect: (1) time context, (2) 3-day sleep summary, "
            "(3) 3-day stress/mood history, (4) 3-day activity and social summaries, "
            "(5) 3-day academic deadlines, and (6) baseline comparisons if needed."
        )

    if cfg.tools.enabled and tools:
        user_prompt = (
            f"Participant: {case['participant_id']} at Decision Time: {case['decision_time']}\n\n"
            f"{plan_section}\n\n"
            "Call the relevant tools now, then output your structured AnalystOutput JSON."
        )
        return llm.complete_json(
            agent="analyst",
            model=cfg.model,
            system=sys_prompt,
            user=user_prompt,
            schema=AnalystOutput,
            tracker=tracker,
            temperature=cfg.temperature,
            tools=tools,
            max_turns=cfg.tools.max_turns,
        )
    else:
        user_prompt = (
            f"Participant: {case['participant_id']} at Decision Time: {case['decision_time']}\n\n"
            f"{plan_section}\n\n"
            f"## Precomputed Evidence Summary\n{json.dumps(precomputed_summary or {}, indent=2)}\n\n"
            "Synthesize this into your structured AnalystOutput JSON."
        )
        return llm.complete_json(
            agent="analyst",
            model=cfg.model,
            system=sys_prompt,
            user=user_prompt,
            schema=AnalystOutput,
            tracker=tracker,
            temperature=cfg.temperature,
        )

