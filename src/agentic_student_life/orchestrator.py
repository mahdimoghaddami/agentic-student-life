"""End-to-end pipeline orchestrator supporting multi-agent, single-agent, and all ablation toggles."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import logging
from pathlib import Path
import threading
import time
from typing import Any

from .agents import (
    AnalystOutput,
    PlannerOutput,
    run_analyst,
    run_critic,
    run_memory_manager,
    run_planner_step,
    run_single_agent,
    run_writer,
)
from .config import RunConfig
from .data.store import DataStore
from .llm import CallTracker, LLMClient
from .memory.store import MemoryStore
from .skills.library import load_skill, make_load_skill_tool, skill_index_text
from .tools import evidence_summary, make_tools, tool_map


def run_case(
    *,
    case: dict[str, Any],
    cfg: RunConfig,
    data_store: DataStore,
    memory_store: MemoryStore,
    llm: LLMClient,
    calls_log_path: Path | None = None,
) -> dict[str, Any]:
    """Execute one evaluation case end-to-end and return its JSONL record."""
    t_start = time.perf_counter()
    cid = case["case_id"]
    uid = case["participant_id"]
    dtime = case["decision_time"]
    mask = case.get("mask") or []
    tracker = CallTracker(case_id=cid, config_id=cfg.config_id, calls_log_path=calls_log_path)

    try:
        view = data_store.get_view(uid, dtime, mask=mask)
        tmap = tool_map(view)
        time_ctx = tmap["get_time_context"]()
        base_tools = make_tools(view)
        mem_text = memory_store.format_for_prompt(
            uid, enabled=cfg.memory.enabled, history_k=cfg.memory.history_k
        )
        mem_snap = memory_store.get_snapshot(
            uid, enabled=cfg.memory.enabled, history_k=cfg.memory.history_k
        )
        s_index = skill_index_text() if cfg.skills.enabled else "Skills disabled: use general supportive coaching."

        plan_steps_all: list[str] = []
        evidence_list: list[dict[str, Any]] = []
        critiques: list[str] = []
        planning_rounds_used = 0
        reflection_rounds_used = 0
        decision = "none"
        skill_used: str | None = None
        final_message: str | None = None

        if cfg.mode == "single_agent":
            sa_tools = list(base_tools)
            if cfg.skills.enabled:
                sa_tools.append(make_load_skill_tool())
            if cfg.memory.enabled:
                sa_tools.append(
                    memory_store.make_recall_tool(
                        uid, enabled=cfg.memory.enabled, history_k=cfg.memory.history_k
                    )
                )
            sa_out = run_single_agent(
                llm=llm,
                cfg=cfg,
                tracker=tracker,
                case=case,
                time_context=time_ctx,
                memory_text=mem_text,
                skill_index=s_index,
                tools=sa_tools,
            )
            decision = sa_out.decision
            skill_used = sa_out.skill_used
            final_message = sa_out.final_message
            plan_steps_all = sa_out.plan
            for ev in sa_out.evidence:
                evidence_list.append(ev.model_dump())

        else:
            analyst_reports: list[AnalystOutput] = []
            planner_decision: PlannerOutput | None = None

            if cfg.planning.enabled and cfg.planning.max_rounds >= 1:
                max_p = cfg.planning.max_rounds
                for r_idx in range(1, max_p + 1):
                    planning_rounds_used = r_idx
                    p_out = run_planner_step(
                        llm=llm,
                        cfg=cfg,
                        tracker=tracker,
                        case=case,
                        time_context=time_ctx,
                        memory_text=mem_text,
                        skill_index=s_index,
                        round_idx=r_idx,
                        max_rounds=max_p,
                        prior_plans=plan_steps_all,
                        analyst_reports=analyst_reports,
                    )
                    for step_txt in p_out.plan_steps:
                        if step_txt not in plan_steps_all:
                            plan_steps_all.append(step_txt)
                    planner_decision = p_out

                    # Always run the Analyst at least once (on Round 1), and again when status == "gather_more"
                    if len(analyst_reports) == 0 or p_out.status == "gather_more":
                        pre_ev = evidence_summary(view) if not cfg.tools.enabled else None
                        a_rep = run_analyst(
                            llm=llm,
                            cfg=cfg,
                            tracker=tracker,
                            case=case,
                            plan_steps=p_out.plan_steps,
                            hypotheses=p_out.hypotheses,
                            tools=base_tools,
                            precomputed_summary=pre_ev,
                        )
                        analyst_reports.append(a_rep)

                    # If we gathered evidence on the final round, let the Planner finalize its decision
                    if len(analyst_reports) > 0 and r_idx == max_p and p_out.status == "gather_more":
                        planner_decision = run_planner_step(
                            llm=llm,
                            cfg=cfg,
                            tracker=tracker,
                            case=case,
                            time_context=time_ctx,
                            memory_text=mem_text,
                            skill_index=s_index,
                            round_idx=r_idx,
                            max_rounds=max_p,
                            prior_plans=plan_steps_all,
                            analyst_reports=analyst_reports,
                        )
                        break

                    if p_out.status == "finalize" and len(analyst_reports) > 0:
                        break
            else:
                # No-planning ablation: Analyst gathers evidence directly
                pre_ev = evidence_summary(view) if not cfg.tools.enabled else None
                a_rep = run_analyst(
                    llm=llm,
                    cfg=cfg,
                    tracker=tracker,
                    case=case,
                    plan_steps=[],
                    hypotheses=[],
                    tools=base_tools,
                    precomputed_summary=pre_ev,
                )
                analyst_reports.append(a_rep)

            for rep in analyst_reports:
                for f_item in rep.findings:
                    evidence_list.append(f_item.model_dump())

            if planner_decision is not None and planner_decision.decision == "none":
                decision = "none"
                skill_used = None
                final_message = None
            else:
                chosen_skill_name = (
                    planner_decision.skill_to_use
                    if (planner_decision and planner_decision.skill_to_use)
                    else ("clarifying_question" if (planner_decision and planner_decision.decision == "ask") else None)
                )
                skill_doc = (
                    load_skill(chosen_skill_name)
                    if (cfg.skills.enabled and chosen_skill_name)
                    else None
                )
                w_out = run_writer(
                    llm=llm,
                    cfg=cfg,
                    tracker=tracker,
                    case=case,
                    memory_text=mem_text,
                    analyst_reports=analyst_reports,
                    planner_decision=planner_decision,
                    skill_doc=skill_doc,
                    skill_index=s_index,
                )
                decision = w_out.decision
                skill_used = w_out.skill_used
                final_message = w_out.final_message

                if (
                    decision in ("suggest", "ask")
                    and final_message
                    and cfg.reflection.enabled
                    and cfg.reflection.max_rounds >= 1
                ):
                    max_r = cfg.reflection.max_rounds
                    for r_cycle in range(1, max_r + 1):
                        reflection_rounds_used = r_cycle
                        c_out = run_critic(
                            llm=llm,
                            cfg=cfg,
                            tracker=tracker,
                            case=case,
                            memory_text=mem_text,
                            analyst_reports=analyst_reports,
                            planner_decision=planner_decision,
                            writer_out=w_out,
                            round_idx=r_cycle,
                            max_rounds=max_r,
                        )
                        critiques.append(f"[{c_out.verdict}] {c_out.critique}")
                        if c_out.verdict == "pass":
                            break
                        w_out = run_writer(
                            llm=llm,
                            cfg=cfg,
                            tracker=tracker,
                            case=case,
                            memory_text=mem_text,
                            analyst_reports=analyst_reports,
                            planner_decision=planner_decision,
                            skill_doc=skill_doc,
                            skill_index=s_index,
                            previous_draft=w_out.final_message,
                            critic_feedback=c_out.revision_instructions or c_out.critique,
                        )
                        final_message = w_out.final_message

        # Append explicit simulated profile & memory evidence items
        prof = mem_snap.get("simulated_profile", {})
        if prof:
            evidence_list.append(
                {
                    "source": "simulated_profile",
                    "detail": f"Goals: {prof.get('goals', [])}; Preferences: {prof.get('preferences', {})}",
                    "simulated": True,
                }
            )
        for lp in mem_snap.get("learned_preferences", []):
            evidence_list.append(
                {
                    "source": "memory.feedback",
                    "detail": lp.get("preference", ""),
                    "simulated": True,
                }
            )

        # Memory Manager: record episode and extract any preference updates from scripted feedback
        scripted_fb = case.get("scripted_feedback")
        extracted_prefs = run_memory_manager(
            llm=llm,
            cfg=cfg,
            tracker=tracker,
            case=case,
            decision=decision,
            skill_used=skill_used,
            final_message=final_message,
            scripted_feedback=scripted_fb,
        )
        memory_updates = memory_store.record_episode(
            uid=uid,
            case_id=cid,
            decision_time=dtime,
            decision=decision,
            skill_used=skill_used,
            final_message=final_message,
            feedback=scripted_fb,
            new_preferences=extracted_prefs,
        )

        elapsed_s = time.perf_counter() - t_start
        return {
            "case_id": cid,
            "participant_id": uid,
            "decision_time": dtime,
            "category": case.get("category", ""),
            "episode_id": case.get("episode_id", cid),
            "step": case.get("step", 1),
            "config_id": cfg.config_id,
            "model": cfg.model,
            "status": "ok",
            "error": None,
            "decision": decision,
            "expected_decision": case.get("expected_decision", []),
            "skill_used": skill_used,
            "plan": plan_steps_all,
            "evidence": evidence_list,
            "final_message": final_message,
            "reflection": {"rounds_used": reflection_rounds_used, "critiques": critiques},
            "planning": {"rounds_used": planning_rounds_used},
            "memory_updates": memory_updates,
            "trace": tracker.summary(elapsed_s),
        }

    except Exception as exc:
        elapsed_s = time.perf_counter() - t_start
        return {
            "case_id": cid,
            "participant_id": uid,
            "decision_time": dtime,
            "category": case.get("category", ""),
            "episode_id": case.get("episode_id", cid),
            "step": case.get("step", 1),
            "config_id": cfg.config_id,
            "model": cfg.model,
            "status": "failed",
            "error": f"{type(exc).__name__}: {exc}",
            "decision": "none",
            "expected_decision": case.get("expected_decision", []),
            "skill_used": None,
            "plan": [],
            "evidence": [],
            "final_message": None,
            "reflection": {"rounds_used": 0, "critiques": []},
            "planning": {"rounds_used": 0},
            "memory_updates": [],
            "trace": tracker.summary(elapsed_s),
        }


def run_suite(
    *,
    cfg: RunConfig,
    cases: list[dict[str, Any]],
    profiles: dict[str, Any],
    out_root: str | Path = "runs",
    cache_dir: str = "cache/features",
    reset_memory: bool = False,
    resume: bool = True,
) -> dict[str, Any]:
    """Run all cases for one `RunConfig`, preserving episode ordering for multi-step preference episodes."""
    run_dir = Path(out_root) / cfg.config_id
    run_dir.mkdir(parents=True, exist_ok=True)
    outputs_path = run_dir / "outputs.jsonl"
    calls_path = run_dir / "calls.jsonl"
    log_path = run_dir / "run.log"
    failed_path = run_dir / "failed_cases.json"
    snap_path = run_dir / "config.snapshot.toml"

    snap_path.write_text(cfg.to_toml(), encoding="utf-8")

    logger = logging.getLogger(f"asl.{cfg.config_id}")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    fh = logging.FileHandler(log_path, encoding="utf-8")
    fh.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
    logger.addHandler(fh)

    memory_store = MemoryStore(run_dir=run_dir, profiles=profiles)
    if reset_memory or not resume:
        memory_store.reset()
        if outputs_path.exists():
            outputs_path.unlink()
        if calls_path.exists():
            calls_path.unlink()

    selected_cases = list(cases)
    if cfg.case_ids:
        allowed = set(cfg.case_ids)
        selected_cases = [c for c in selected_cases if c["case_id"] in allowed]

    existing_ok: dict[str, dict[str, Any]] = {}
    if resume and outputs_path.exists():
        for line in outputs_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            rec = json.loads(line)
            if rec.get("status") == "ok":
                existing_ok[rec["case_id"]] = rec

    # Group cases by episode_id so steps within an episode run sequentially in step order
    episodes: dict[str, list[dict[str, Any]]] = {}
    for c in selected_cases:
        ep_id = c.get("episode_id") or c["case_id"]
        episodes.setdefault(ep_id, []).append(c)
    for ep_list in episodes.values():
        ep_list.sort(key=lambda x: int(x.get("step", 1)))

    data_store = DataStore(cache_dir=cache_dir)
    llm = LLMClient()
    write_lock = threading.Lock()
    results_by_id: dict[str, dict[str, Any]] = dict(existing_ok)

    def _run_episode(ep_cases: list[dict[str, Any]]) -> list[dict[str, Any]]:
        ep_out = []
        for c in ep_cases:
            cid = c["case_id"]
            if cid in existing_ok:
                logger.info("Skipping already-completed case %s", cid)
                ep_out.append(existing_ok[cid])
                continue
            logger.info("Starting case %s (%s @ %s, category=%s)", cid, c["participant_id"], c["decision_time"], c.get("category"))
            res = run_case(
                case=c,
                cfg=cfg,
                data_store=data_store,
                memory_store=memory_store,
                llm=llm,
                calls_log_path=calls_path,
            )
            with write_lock:
                results_by_id[cid] = res
                with outputs_path.open("a", encoding="utf-8") as f:
                    f.write(json.dumps(res) + "\n")
            logger.info(
                "Finished case %s: status=%s decision=%s expected=%s latency=%.2fs tokens=%d",
                cid,
                res["status"],
                res["decision"],
                res["expected_decision"],
                res["trace"]["latency_s"],
                res["trace"]["total_tokens"],
            )
            ep_out.append(res)
        return ep_out

    with ThreadPoolExecutor(max_workers=max(1, cfg.max_workers)) as pool:
        futs = [pool.submit(_run_episode, ep_list) for ep_list in episodes.values()]
        for fut in as_completed(futs):
            fut.result()

    # Rewrite outputs.jsonl sorted by case_id for clean deterministic ordering
    ordered_records = [results_by_id[c["case_id"]] for c in selected_cases if c["case_id"] in results_by_id]
    with outputs_path.open("w", encoding="utf-8") as f:
        for rec in ordered_records:
            f.write(json.dumps(rec) + "\n")

    failed = [
        {"case_id": r["case_id"], "participant_id": r["participant_id"], "error": r["error"]}
        for r in ordered_records
        if r.get("status") != "ok"
    ]
    failed_path.write_text(json.dumps(failed, indent=2), encoding="utf-8")

    ok_count = len(ordered_records) - len(failed)
    summary = {
        "config_id": cfg.config_id,
        "total_cases": len(ordered_records),
        "ok_cases": ok_count,
        "failed_cases": len(failed),
        "failed_details": failed,
        "outputs_path": str(outputs_path),
    }
    logger.info("Run %s complete: %d ok / %d failed", cfg.config_id, ok_count, len(failed))
    return summary

