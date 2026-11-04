"""Metrics computation across evaluation runs and ablation configurations."""

from __future__ import annotations

import json
from pathlib import Path
import re
from typing import Any

import numpy as np


def _mean_std(vals: list[float]) -> tuple[float, float]:
    if not vals:
        return 0.0, 0.0
    arr = np.array(vals, dtype=float)
    m = float(np.mean(arr))
    s = float(np.std(arr, ddof=1)) if len(arr) > 1 else 0.0
    return round(m, 2), round(s, 2)


def check_preference_adherence(rec: dict[str, Any], case: dict[str, Any]) -> bool | None:
    """For preference_update steps >= 2, check whether the generated message avoids
    forbidden terms from prior feedback and includes at least one required theme."""
    if case.get("category") != "preference_update" or int(case.get("step", 1)) < 2:
        return None
    msg = (rec.get("final_message") or "").lower()
    if not msg:
        return False
    # Strip non-exercise English idioms ('running high', 'running low', 'running on', 'running late', 'long run')
    msg_clean = re.sub(r"\brunning\s+(?:high|low|on|late|out|behind)\b", "", msg)
    msg_clean = re.sub(r"\blong\s+run\b", "", msg_clean)
    fb = case.get("scripted_feedback") or {}
    forbidden = fb.get("forbidden_terms") or case.get("forbidden_terms") or []
    for term in forbidden:
        # Word-boundary check so 'run' doesn't false-trigger on 'crunch'
        pat = r"\b" + re.escape(term.lower()) + r"\b"
        if re.search(pat, msg_clean):
            return False
    return True


def compute_run_metrics(
    run_dir: str | Path,
    cases_by_id: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """Compute comprehensive metrics for a single run directory (`runs/<config_id>`)."""
    rdir = Path(run_dir)
    out_path = rdir / "outputs.jsonl"
    judge_path = rdir / "judge_scores.jsonl"
    if not out_path.exists():
        return {"config_id": rdir.name, "available": False}

    records = [
        json.loads(line)
        for line in out_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    judge_map: dict[str, dict[str, Any]] = {}
    if judge_path.exists():
        for line in judge_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                obj = json.loads(line)
                judge_map[obj["case_id"]] = obj

    n_total = len(records)
    ok_recs = [r for r in records if r.get("status") == "ok"]
    n_ok = len(ok_recs)
    success_rate = round(100.0 * n_ok / n_total, 1) if n_total else 0.0

    # Decision accuracy (overall and per category)
    correct_flags = []
    by_category: dict[str, list[dict[str, Any]]] = {}
    confusion: dict[str, dict[str, int]] = {
        exp: {"suggest": 0, "ask": 0, "none": 0}
        for exp in ("suggest", "ask", "none")
    }
    pref_checks: list[bool] = []

    for r in records:
        cid = r["case_id"]
        case = cases_by_id.get(cid, {})
        exp_list = r.get("expected_decision") or case.get("expected_decision") or []
        pred = r.get("decision", "none")
        is_correct = (r.get("status") == "ok") and (pred in exp_list)
        correct_flags.append(1.0 if is_correct else 0.0)
        cat = r.get("category") or case.get("category") or "other"
        by_category.setdefault(cat, []).append(r)
        if exp_list:
            primary_exp = pred if pred in exp_list else exp_list[0]
            if primary_exp in confusion and pred in confusion[primary_exp]:
                confusion[primary_exp][pred] += 1
        pa = check_preference_adherence(r, case)
        if pa is not None:
            pref_checks.append(pa)

    decision_acc = round(100.0 * float(np.mean(correct_flags)), 1) if correct_flags else 0.0
    pref_adherence_rate = (
        round(100.0 * float(np.mean([1.0 if x else 0.0 for x in pref_checks])), 1)
        if pref_checks
        else 100.0
    )

    # Judge scores
    ca_vals = [float(j["context_awareness"]) for j in judge_map.values()]
    ga_vals = [float(j["goal_alignment"]) for j in judge_map.values()]
    cl_vals = [float(j["clarity"]) for j in judge_map.values()]
    jm_vals = [float(j["mean_score"]) for j in judge_map.values()]

    ca_mean, ca_std = _mean_std(ca_vals)
    ga_mean, ga_std = _mean_std(ga_vals)
    cl_mean, cl_std = _mean_std(cl_vals)
    jm_mean, jm_std = _mean_std(jm_vals)

    # Efficiency metrics across all cases
    lat_vals = [float(r.get("trace", {}).get("latency_s", 0.0)) for r in ok_recs]
    call_vals = [float(r.get("trace", {}).get("llm_calls", 0)) for r in ok_recs]
    tool_vals = [float(r.get("trace", {}).get("tool_calls", 0)) for r in ok_recs]
    tok_vals = [float(r.get("trace", {}).get("total_tokens", 0)) for r in ok_recs]
    plan_rounds = [float(r.get("planning", {}).get("rounds_used", 0)) for r in ok_recs]
    refl_rounds = [
        float(r.get("reflection", {}).get("rounds_used", 0))
        for r in ok_recs
        if r.get("final_message")
    ]

    lat_mean, lat_std = _mean_std(lat_vals)
    call_mean, call_std = _mean_std(call_vals)
    tool_mean, tool_std = _mean_std(tool_vals)
    tok_mean, tok_std = _mean_std(tok_vals)
    plan_r_mean, _ = _mean_std(plan_rounds)
    refl_r_mean, _ = _mean_std(refl_rounds)

    # Category breakdown
    cat_metrics: dict[str, Any] = {}
    for cat, crecs in by_category.items():
        c_corr = [
            1.0 if (r.get("status") == "ok" and r.get("decision") in (r.get("expected_decision") or [])) else 0.0
            for r in crecs
        ]
        c_j = [judge_map[r["case_id"]] for r in crecs if r["case_id"] in judge_map]
        c_ca, _ = _mean_std([float(x["context_awareness"]) for x in c_j])
        c_ga, _ = _mean_std([float(x["goal_alignment"]) for x in c_j])
        c_cl, _ = _mean_std([float(x["clarity"]) for x in c_j])
        c_jm, _ = _mean_std([float(x["mean_score"]) for x in c_j])
        c_lat, _ = _mean_std([float(r.get("trace", {}).get("latency_s", 0.0)) for r in crecs if r.get("status") == "ok"])
        c_calls, _ = _mean_std([float(r.get("trace", {}).get("llm_calls", 0)) for r in crecs if r.get("status") == "ok"])
        c_toks, _ = _mean_std([float(r.get("trace", {}).get("total_tokens", 0)) for r in crecs if r.get("status") == "ok"])
        cat_metrics[cat] = {
            "n_cases": len(crecs),
            "n_scored_messages": len(c_j),
            "decision_acc": round(100.0 * float(np.mean(c_corr)), 1) if c_corr else 0.0,
            "context_awareness": c_ca,
            "goal_alignment": c_ga,
            "clarity": c_cl,
            "judge_mean": c_jm,
            "latency_mean": c_lat,
            "calls_mean": c_calls,
            "tokens_mean": c_toks,
        }

    return {
        "config_id": rdir.name,
        "available": True,
        "n_cases": n_total,
        "n_ok": n_ok,
        "success_rate": success_rate,
        "decision_acc": decision_acc,
        "pref_adherence_rate": pref_adherence_rate,
        "n_judged": len(judge_map),
        "context_awareness": {"mean": ca_mean, "std": ca_std, "values": ca_vals},
        "goal_alignment": {"mean": ga_mean, "std": ga_std, "values": ga_vals},
        "clarity": {"mean": cl_mean, "std": cl_std, "values": cl_vals},
        "judge_mean": {"mean": jm_mean, "std": jm_std, "values": jm_vals},
        "latency_s": {"mean": lat_mean, "std": lat_std, "values": lat_vals},
        "llm_calls": {"mean": call_mean, "std": call_std, "values": call_vals},
        "tool_calls": {"mean": tool_mean, "std": tool_std, "values": tool_vals},
        "total_tokens": {"mean": tok_mean, "std": tok_std, "values": tok_vals},
        "planning_rounds_mean": plan_r_mean,
        "reflection_rounds_mean": refl_r_mean,
        "confusion": confusion,
        "by_category": cat_metrics,
    }

