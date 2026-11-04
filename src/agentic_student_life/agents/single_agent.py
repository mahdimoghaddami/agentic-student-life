"""Single-Agent baseline coach (all tools, skills, and memory in a single LLM tool loop)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

from ..config import RunConfig
from ..llm import CallTracker, LLMClient
from .schemas import SingleAgentOutput

PROMPT_PATH = Path("prompts/single_agent.md")


def load_single_agent_prompt() -> str:
    if PROMPT_PATH.exists():
        return PROMPT_PATH.read_text(encoding="utf-8")
    return "You are an AI stress-management coach for college students."


def run_single_agent(
    *,
    llm: LLMClient,
    cfg: RunConfig,
    tracker: CallTracker,
    case: dict[str, Any],
    time_context: dict[str, Any],
    memory_text: str,
    skill_index: str,
    tools: list[Callable],
) -> SingleAgentOutput:
    """Run the single-agent baseline with the same observations, profile/history, and tools."""
    sys_prompt = load_single_agent_prompt()
    extra_case_note = ""
    if case.get("recent_interaction_note"):
        extra_case_note = f"\n### Recent Interaction Context Note:\n{case['recent_interaction_note']}\n"

    user_prompt = (
        f"## Case Context\n"
        f"- Case ID: {case['case_id']}\n"
        f"- Participant: {case['participant_id']}\n"
        f"- Decision Time: {case['decision_time']}\n"
        f"- Time Context: {json.dumps(time_context)}\n"
        f"{extra_case_note}\n"
        f"{memory_text}\n\n"
        f"## Available Coaching Skills (call `load_skill(name)` tool for full instructions)\n"
        f"{skill_index}\n\n"
        "Use your tools to inspect the student's sleep, stress/mood, activity, social interaction, and deadlines, "
        "then output your final SingleAgentOutput JSON."
    )

    out = llm.complete_json(
        agent="single_agent",
        model=cfg.model,
        system=sys_prompt,
        user=user_prompt,
        schema=SingleAgentOutput,
        tracker=tracker,
        temperature=cfg.temperature,
        tools=tools if cfg.tools.enabled else None,
        max_turns=cfg.tools.max_turns + 2,
    )
    if out.decision == "none":
        out.final_message = None
        out.skill_used = None
    return out

