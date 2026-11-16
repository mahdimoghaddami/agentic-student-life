"""Planner (Coach Strategist) agent."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..config import RunConfig
from ..llm import CallTracker, LLMClient
from .schemas import AnalystOutput, PlannerOutput

PROMPT_PATH = Path("prompts/planner.md")


def load_planner_prompt() -> str:
    if PROMPT_PATH.exists():
        return PROMPT_PATH.read_text(encoding="utf-8")
    return "You are the Planner in a multi-agent student stress-coaching system."


def run_planner_step(
    *,
    llm: LLMClient,
    cfg: RunConfig,
    tracker: CallTracker,
    case: dict[str, Any],
    time_context: dict[str, Any],
    memory_text: str,
    skill_index: str,
    round_idx: int,
    max_rounds: int,
    prior_plans: list[str],
    analyst_reports: list[AnalystOutput],
) -> PlannerOutput:
    """Run one planning round (`round_idx` in 1..max_rounds)."""
    sys_prompt = load_planner_prompt()
    can_gather_more = round_idx < max_rounds and len(analyst_reports) > 0

    evidence_text = "No analyst tool evidence gathered yet (this is the initial planning step)."
    if analyst_reports:
        ev_blocks = []
        for i, rep in enumerate(analyst_reports, 1):
            ev_blocks.append(f"--- Analyst Report (Round {i}) ---\n{rep.model_dump_json(indent=2)}")
        evidence_text = "\n\n".join(ev_blocks)

    if len(analyst_reports) == 0:
        stage_instruction = (
            f"STAGE: Initial Information-Gathering Plan (Round {round_idx} of {max_rounds}).\n"
            "Propose 2-4 concrete `plan_steps` for the Context Analyst to check using its tools "
            "(e.g. sleep summary, stress/mood history, academic deadlines, activity/social summary, baseline comparison). "
            "Set `status = 'gather_more'` and provide a provisional `decision`."
        )
    elif can_gather_more:
        stage_instruction = (
            f"STAGE: Evidence Review & Deepening Plan (Round {round_idx} of {max_rounds}).\n"
            "Inspect the Analyst Report(s) so far. Because additional planning budget remains "
            f"(round {round_idx} < max_rounds={max_rounds}), check whether a follow-up verification pass "
            "(such as `compare_to_baseline` on sleep/activity/conversation, 7-day trend check, social summary, "
            "or `search_campus_resources`) would strengthen the evidence before finalizing. "
            "Set `status = 'gather_more'` with 1-2 targeted follow-up `plan_steps` to deepen the analysis, "
            "or `status = 'finalize'` if the case is already completely unambiguous."
        )
    else:
        stage_instruction = (
            f"STAGE: Final Strategy Decision (Round {round_idx} of {max_rounds} — MUST FINALIZE).\n"
            "You MUST set `status = 'finalize'` now and commit to your final `decision` "
            "('suggest', 'ask', or 'none'), `skill_to_use`, `target_goal`, and detailed `writer_guidance`."
        )

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
        f"## Available Coaching Skills\n{skill_index}\n\n"
        f"## Prior Plan Steps\n{json.dumps(prior_plans)}\n\n"
        f"## Evidence Gathered So Far\n{evidence_text}\n\n"
        f"## Current Task\n{stage_instruction}"
    )

    out = llm.complete_json(
        agent="planner",
        model=cfg.model,
        system=sys_prompt,
        user=user_prompt,
        schema=PlannerOutput,
        tracker=tracker,
        temperature=cfg.temperature,
    )
    if not can_gather_more and len(analyst_reports) > 0:
        out.status = "finalize"
    return out

