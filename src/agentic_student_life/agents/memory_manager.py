"""Memory Manager agent (extracts learned preferences from simulated student feedback)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..config import RunConfig
from ..llm import CallTracker, LLMClient
from .schemas import MemoryUpdateOutput

PROMPT_PATH = Path("prompts/memory.md")


def load_memory_prompt() -> str:
    if PROMPT_PATH.exists():
        return PROMPT_PATH.read_text(encoding="utf-8")
    return "You are the Memory Manager in a multi-agent student stress-coaching system."


def run_memory_manager(
    *,
    llm: LLMClient,
    cfg: RunConfig,
    tracker: CallTracker,
    case: dict[str, Any],
    decision: str,
    skill_used: str | None,
    final_message: str | None,
    scripted_feedback: dict[str, Any] | None,
) -> list[str]:
    """Extract learned preferences from scripted student feedback (if present)."""
    if not scripted_feedback or not cfg.memory.enabled:
        return []
    fb_text = scripted_feedback.get("feedback_text", "")
    if not fb_text:
        return []

    sys_prompt = load_memory_prompt()
    user_prompt = (
        f"## Completed Interaction Episode\n"
        f"- Case ID: {case['case_id']}\n"
        f"- Participant: {case['participant_id']}\n"
        f"- Decision Time: {case['decision_time']}\n"
        f"- Coach Decision: {decision} (skill={skill_used})\n"
        f"- Coach Message: {final_message!r}\n\n"
        f"## Simulated Student Feedback (SIMULATED=true)\n"
        f"{json.dumps(scripted_feedback, indent=2)}\n\n"
        "Extract 1-3 crisp, imperative `new_preferences` rules so future coaching episodes strictly obey this feedback."
    )

    out = llm.complete_json(
        agent="memory_manager",
        model=cfg.model,
        system=sys_prompt,
        user=user_prompt,
        schema=MemoryUpdateOutput,
        tracker=tracker,
        temperature=0.1,
    )
    return out.new_preferences

