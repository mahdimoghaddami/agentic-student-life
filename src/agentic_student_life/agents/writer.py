"""Message Writer (Coach) agent."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..config import RunConfig
from ..llm import CallTracker, LLMClient
from ..skills.library import make_load_skill_tool
from .schemas import AnalystOutput, PlannerOutput, WriterOutput

PROMPT_PATH = Path("prompts/writer.md")


def load_writer_prompt() -> str:
    if PROMPT_PATH.exists():
        return PROMPT_PATH.read_text(encoding="utf-8")
    return "You are the Message Writer in a multi-agent student stress-coaching system."


def run_writer(
    *,
    llm: LLMClient,
    cfg: RunConfig,
    tracker: CallTracker,
    case: dict[str, Any],
    memory_text: str,
    analyst_reports: list[AnalystOutput],
    planner_decision: PlannerOutput | None,
    skill_doc: dict[str, Any] | None,
    skill_index: str,
    previous_draft: str | None = None,
    critic_feedback: str | None = None,
) -> WriterOutput:
    """Draft or revise the final coaching message (or choose the decision when Planner is disabled)."""
    sys_prompt = load_writer_prompt()

    ev_text = "\n\n".join(rep.model_dump_json(indent=2) for rep in analyst_reports)
    extra_case_note = ""
    if case.get("recent_interaction_note"):
        extra_case_note = f"\n### Recent Interaction Context Note:\n{case['recent_interaction_note']}\n"

    if planner_decision is not None:
        plan_blk = (
            f"## Planner Strategy Decision\n"
            f"- Decision: {planner_decision.decision}\n"
            f"- Skill to Use: {planner_decision.skill_to_use}\n"
            f"- Target Goal: {planner_decision.target_goal}\n"
            f"- Writer Guidance: {planner_decision.writer_guidance}\n"
            f"- Rationale: {planner_decision.rationale}\n"
        )
    else:
        plan_blk = (
            "## No-Planner Mode: You Must Also Select the Decision & Skill\n"
            "- Choose `decision = 'suggest'` if stress >= 4, sleep < 6.5h, or deadlines are approaching.\n"
            "- Choose `decision = 'ask'` (skill='clarifying_question') if key modalities (sleep, activity, stress) are missing.\n"
            "- Choose `decision = 'none'` (`final_message = null`) if the student is doing fine (stress <= 2.5, good sleep, low deadlines) or a recent coaching message was already accepted.\n"
            f"\nAvailable Skills:\n{skill_index}\n"
        )

    if cfg.skills.enabled and skill_doc:
        skill_blk = (
            f"## Loaded Skill Instructions (`{skill_doc.get('name')}`)\n"
            f"Description: {skill_doc.get('description')}\n"
            f"When to use: {skill_doc.get('when_to_use')}\n"
            f"Contraindications: {skill_doc.get('contraindications')}\n\n"
            f"{skill_doc.get('body', '')}\n"
        )
    else:
        skill_blk = (
            "## Skill Instructions: Select a skill from the index and call load_skill for its full "
            "procedure before drafting." if cfg.skills.enabled
            else "## Skill Instructions: Generic supportive coaching (Skills module disabled)."
        )

    revision_blk = ""
    if previous_draft is not None and critic_feedback is not None:
        revision_blk = (
            f"\n## REVISION REQUIRED (Critic Feedback on Previous Draft)\n"
            f"- Previous Draft: {previous_draft!r}\n"
            f"- Critic Revision Instructions: {critic_feedback}\n"
            "Fix every single issue identified by the Critic while preserving warmth and factual grounding.\n"
        )

    user_prompt = (
        f"## Case: {case['case_id']} | Participant: {case['participant_id']} | Time: {case['decision_time']}\n"
        f"{extra_case_note}\n"
        f"{memory_text}\n\n"
        f"{plan_blk}\n"
        f"{skill_blk}\n"
        f"## Analyst Evidence Reports\n{ev_text}\n"
        f"{revision_blk}\n"
        "Output your structured WriterOutput JSON."
    )

    out = llm.complete_json(
        agent="writer",
        model=cfg.model,
        system=sys_prompt,
        user=user_prompt,
        schema=WriterOutput,
        tracker=tracker,
        temperature=cfg.temperature,
        tools=[make_load_skill_tool()] if cfg.skills.enabled and
              (skill_doc is None or previous_draft is not None) else None,
        max_turns=cfg.tools.max_turns,
    )
    if planner_decision is not None and previous_draft is None:
        out.decision = planner_decision.decision
        if out.decision == "none":
            out.final_message = None
            out.skill_used = None
        elif not out.skill_used:
            out.skill_used = planner_decision.skill_to_use
    elif out.decision == "none":
        out.final_message = None
        out.skill_used = None
    return out

