"""Independent LLM-as-a-Judge evaluator for non-null coaching messages."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
import json
from pathlib import Path
import threading
from typing import Any

from pydantic import BaseModel, Field

from ..config import JudgeConfig
from ..llm import CallTracker, LLMClient
from ..provenance import digest
from .context import evaluation_payload, message_fingerprint

PROMPT_PATH = Path(__file__).resolve().parents[3] / "prompts/judge.md"


class JudgeOutput(BaseModel):
    context_awareness: int = Field(ge=1, le=5, description="Score 1-5 on context awareness")
    goal_alignment: int = Field(ge=1, le=5, description="Score 1-5 on goal alignment and preference compliance")
    clarity: int = Field(ge=1, le=5, description="Score 1-5 on clarity, warmth, and actionability")
    decision_appropriate: bool = Field(description="Whether sending this suggest/ask message was appropriate")
    justification: str = Field(description="Concise 1-2 sentence explanation of the scores")


def load_judge_prompt() -> str:
    if PROMPT_PATH.exists():
        return PROMPT_PATH.read_text(encoding="utf-8")
    raise FileNotFoundError(f"Missing judge rubric: {PROMPT_PATH}")


def score_fingerprint(rec, cfg):
    return digest({"message": message_fingerprint(rec), "rubric": load_judge_prompt(),
                   "judge_model": cfg.model, "temperature": cfg.temperature})


def judge_single_record(
    *,
    rec: dict[str, Any],
    case: dict[str, Any],
    profile: dict[str, Any],
    llm: LLMClient,
    judge_cfg: JudgeConfig,
) -> dict[str, Any]:
    """Score one non-null `final_message` using the fixed Judge model."""
    uid = rec["participant_id"]
    dtime = rec["decision_time"]
    user_prompt = json.dumps(evaluation_payload(rec), indent=2)
    tracker = CallTracker(rec["case_id"], rec["config_id"])

    out = llm.complete_json(
        agent="judge",
        model=judge_cfg.model,
        system=load_judge_prompt(),
        user=user_prompt,
        schema=JudgeOutput,
        tracker=tracker,
        temperature=judge_cfg.temperature,
    )
    if tracker.models_used != {judge_cfg.model}:
        raise ValueError("Judge call did not record the configured model")
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
        "message_fingerprint": message_fingerprint(rec),
        "evaluation_fingerprint": score_fingerprint(rec, judge_cfg),
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

    for rec in scorable:
        evaluation_payload(rec)  # Reject missing context before making any paid calls.
    llm = LLMClient()
    lock = threading.Lock()
    results_map: dict[str, dict[str, Any]] = dict(existing)

    def _work(rec: dict[str, Any]) -> dict[str, Any]:
        cid = rec["case_id"]
        if cid in existing and existing[cid].get("evaluation_fingerprint") == score_fingerprint(rec, jcfg):
            return existing[cid]
        case = cases_by_id.get(cid, {"case_id": cid, "mask": []})
        prof = profiles.get(rec["participant_id"], {})
        scored = judge_single_record(
            rec=rec,
            case=case,
            profile=prof,
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

