"""Critic (Reflection Reviewer) agent."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ..config import RunConfig
from ..llm import CallTracker, LLMClient
from .schemas import AnalystOutput, CriticOutput, PlannerOutput, WriterOutput

PROMPT_PATH = Path("prompts/critic.md")


def load_critic_prompt() -> str:
    if PROMPT_PATH.exists():
        return PROMPT_PATH.read_text(encoding="utf-8")
    return "You are the Critic in a multi-agent student stress-coaching system."


def run_critic(
    *,
    llm: LLMClient,
    cfg: RunConfig,
    tracker: CallTracker,
    case: dict[str, Any],
    memory_text: str,
    analyst_reports: list[AnalystOutput],
    planner_decision: PlannerOutput | None,
    writer_out: WriterOutput,
    round_idx: int,
    max_rounds: int,
) -> CriticOutput:
    """Audit the Writer's draft message and return pass or revise with instructions."""
    sys_prompt = load_critic_prompt()
    ev_text = "\n\n".join(rep.model_dump_json(indent=2) for rep in analyst_reports)
    plan_txt = planner_decision.model_dump_json(indent=2) if planner_decision else "No Planner used."

    strictness_note = ""
    if round_idx < max_rounds:
        strictness_note = (
            f"\nNote: This is review cycle {round_idx} of {max_rounds}. Apply a rigorous standard: "
            "if the draft can better cite a concrete number/trend from the Analyst evidence, tighten its length, "
            "or more explicitly honor a student goal or learned preference, return `verdict = 'revise'` with "
            "specific improvement instructions."
        )

    user_prompt = (
        f"## Case: {case['case_id']} | Participant: {case['participant_id']} | Time: {case['decision_time']}\n\n"
        f"{memory_text}\n\n"
        f"## Planner Strategy\n{plan_txt}\n\n"
        f"## Analyst Evidence\n{ev_text}\n\n"
        f"## Writer Draft to Audit (Cycle {round_idx}/{max_rounds})\n"
        f"- Decision: {writer_out.decision}\n"
        f"- Skill Used: {writer_out.skill_used}\n"
        f"- Final Message Draft: {writer_out.final_message!r}\n"
        f"{strictness_note}\n\n"
        "Return your CriticOutput JSON."
    )

    return llm.complete_json(
        agent="critic",
        model=cfg.model,
        system=sys_prompt,
        user=user_prompt,
        schema=CriticOutput,
        tracker=tracker,
        temperature=0.1,
    )

