"""Independent LLM-as-a-Judge evaluator for non-null coaching messages."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
import json
from pathlib import Path
import threading
from typing import Any

from pydantic import BaseModel, Field

from ..config import JudgeConfig
from ..data.store import DataStore
from ..llm import LLMClient
from ..tools import evidence_summary

PROMPT_PATH = Path("prompts/judge.md")


class JudgeOutput(BaseModel):
    context_awareness: int = Field(ge=1, le=5, description="Score 1-5 on context awareness")
    goal_alignment: int = Field(ge=1, le=5, description="Score 1-5 on goal alignment and preference compliance")
    clarity: int = Field(ge=1, le=5, description="Score 1-5 on clarity, warmth, and actionability")
    decision_appropriate: bool = Field(description="Whether sending this suggest/ask message was appropriate")
    justification: str = Field(description="Concise 1-2 sentence explanation of the scores")


def load_judge_prompt() -> str:
    if PROMPT_PATH.exists():
        return PROMPT_PATH.read_text(encoding="utf-8")
    return "You are an impartial LLM judge scoring coaching messages from 1 to 5."


def judge_single_record(
    *,
    rec: dict[str, Any],
    case: dict[str, Any],
    profile: dict[str, Any],
    data_store: DataStore,
    llm: LLMClient,
    judge_cfg: JudgeConfig,
) -> dict[str, Any]:
    """Score one non-null `final_message` using the fixed Judge model."""
    uid = rec["participant_id"]
    dtime = rec["decision_time"]
    mask = case.get("mask") or []
    view = data_store.get_view(uid, dtime, mask=mask)
    det_evidence = evidence_summary(view)

    mem_feedback_items = [
        ev.get("detail", "")
        for ev in rec.get("evidence", [])
        if ev.get("source") == "memory.feedback"
    ]

    user_prompt = (
        f"## Case Context\n"
        f"- Case ID: {rec['case_id']}\n"
        f"- Category: {rec.get('category', '')}\n"
        f"- Participant: {uid}\n"
        f"- Decision Time: {dtime}\n"
        f"- Masked Modalities: {json.dumps(mask)}\n"
        f"- Expected Decision Set: {json.dumps(case.get('expected_decision', []))}\n"
        f"- Case Rationale: {case.get('rationale', '')}\n\n"
        f"## Student Simulated Profile (SIMULATED=true)\n"
        f"{json.dumps(profile, indent=2)}\n\n"
        f"## Learned Preferences in Memory at Decision Time (SIMULATED=true)\n"
        f"{json.dumps(mem_feedback_items, indent=2)}\n\n"
        f"## Deterministic Tool Evidence Summary up to Decision Time\n"
        f"{json.dumps(det_evidence, indent=2)}\n\n"
        f"## Coaching System Output to Evaluate\n"
        f"- Decision: {rec['decision']}\n"
        f"- Skill Used: {rec.get('skill_used')}\n"
        f"- Final Message: {rec['final_message']!r}\n\n"
        "Rate this message from 1 to 5 on `context_awareness`, `goal_alignment`, and `clarity`, "
        "plus `decision_appropriate` and `justification`."
    )

    out = llm.complete_json(
        agent="judge",
        model=judge_cfg.model,
        system=load_judge_prompt(),
        user=user_prompt,
        schema=JudgeOutput,
        tracker=None,
        temperature=judge_cfg.temperature,
    )
    mean_score = round((out.context_awareness + out.goal_alignment + out.clarity) / 3.0, 3)
    return {
        "case_id": rec["case_id"],
        "config_id": rec["config_id"],
        "participant_id": uid,
        "decision_time": dtime,
        "category": rec.get("category", ""),
        "decision": rec["decision"],
        "final_message": rec["final_message"],
        "judge_model": judge_cfg.model,
        "context_awareness": out.context_awareness,
        "goal_alignment": out.goal_alignment,
        "clarity": out.clarity,
        "mean_score": mean_score,
        "decision_appropriate": out.decision_appropriate,
        "justification": out.justification,
    }


def judge_run(
    *,
    run_dir: str | Path,
    cases_by_id: dict[str, dict[str, Any]],
    profiles: dict[str, Any],
    judge_cfg: JudgeConfig | None = None,
    cache_dir: str = "cache/features",
    resume: bool = True,
) -> list[dict[str, Any]]:
    """Evaluate all non-null messages in `run_dir/outputs.jsonl` and save `run_dir/judge_scores.jsonl`."""
    rdir = Path(run_dir)
    outputs_path = rdir / "outputs.jsonl"
    scores_path = rdir / "judge_scores.jsonl"
    if not outputs_path.exists():
        raise FileNotFoundError(f"Missing outputs file: {outputs_path}")

    jcfg = judge_cfg or JudgeConfig.from_toml()
    records = [
        json.loads(line)
        for line in outputs_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    scorable = [
        r for r in records
        if r.get("status") == "ok" and r.get("final_message") and str(r.get("final_message")).strip()
    ]

    existing: dict[str, dict[str, Any]] = {}
    if resume and scores_path.exists():
        for line in scores_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                obj = json.loads(line)
                existing[obj["case_id"]] = obj

    data_store = DataStore(cache_dir=cache_dir)
    llm = LLMClient()
    lock = threading.Lock()
    results_map: dict[str, dict[str, Any]] = dict(existing)

    def _work(rec: dict[str, Any]) -> dict[str, Any]:
        cid = rec["case_id"]
        if cid in existing:
            return existing[cid]
        case = cases_by_id.get(cid, {"case_id": cid, "mask": []})
        prof = profiles.get(rec["participant_id"], {})
        scored = judge_single_record(
            rec=rec,
            case=case,
            profile=prof,
            data_store=data_store,
            llm=llm,
            judge_cfg=jcfg,
        )
        with lock:
            results_map[cid] = scored
            with scores_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(scored) + "\n")
        return scored

    with ThreadPoolExecutor(max_workers=max(1, jcfg.max_workers)) as pool:
        futs = [pool.submit(_work, r) for r in scorable]
        for fut in as_completed(futs):
            fut.result()

    ordered = [results_map[r["case_id"]] for r in scorable if r["case_id"] in results_map]
    with scores_path.open("w", encoding="utf-8") as f:
        for obj in ordered:
            f.write(json.dumps(obj) + "\n")
    return ordered

