"""Command-line interface (`asl`) for the Multi-Agent StudentLife Stress Coach."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil

from .cases.build import build_cases, load_cases, load_profiles
from .config import JudgeConfig, load_ablation_configs, load_run_config
from .data.features import preprocess
from .eval import (
    compute_human_vs_llm,
    compute_run_metrics,
    export_human_sheet,
    generate_all_plots,
    generate_all_tables,
    judge_run,
)
from .orchestrator import run_suite


def cmd_preprocess(args: argparse.Namespace) -> None:
    res = preprocess(data_dir=args.data_dir, out_dir=args.out_dir, verbose=True)
    print(f"Preprocessed {len(res.get('uids', []))} participants into {args.out_dir}")


def cmd_cases(args: argparse.Namespace) -> None:
    out = Path(args.out_dir)
    built = build_cases(
        cache_dir=args.cache_dir,
        cases_path=out / "cases.jsonl",
        profiles_path=out / "profiles.json",
        feedback_path=out / "feedback_scripts.json",
    )
    print(f"Generated {len(built)} cases and {len(load_profiles(out / 'profiles.json'))} profiles in {out}/")


def cmd_run(args: argparse.Namespace) -> None:
    cfg = load_run_config(args.config)
    if args.run_id:
        cfg.config_id = args.run_id
    if args.workers:
        cfg.max_workers = args.workers
    cases = load_cases(args.cases)
    profiles = load_profiles(args.profiles)
    summary = run_suite(
        cfg=cfg,
        cases=cases,
        profiles=profiles,
        out_root=args.out_root,
        cache_dir=args.cache_dir,
        reset_memory=args.reset_memory,
        resume=not args.no_resume,
    )
    print(
        f"[{summary['config_id']}] Completed: {summary['ok_cases']} ok / "
        f"{summary['failed_cases']} failed -> {summary['outputs_path']}"
    )
    if summary["failed_cases"] > 0:
        print("Failed cases:", json.dumps(summary["failed_details"], indent=2))
    if args.judge:
        cases_by_id = {c["case_id"]: c for c in cases}
        jcfg = JudgeConfig.from_toml(args.judge_config)
        scores = judge_run(
            run_dir=Path(args.out_root) / cfg.config_id,
            cases_by_id=cases_by_id,
            profiles=profiles,
            judge_cfg=jcfg,
            cache_dir=args.cache_dir,
            resume=not args.no_resume,
        )
        print(f"[{cfg.config_id}] Judged {len(scores)} non-null messages.")


def cmd_ablate(args: argparse.Namespace) -> None:
    all_cfgs = load_ablation_configs(args.config)
    if args.only:
        wanted = [x.strip() for x in args.only.split(",") if x.strip()]
        all_cfgs = {k: v for k, v in all_cfgs.items() if k in wanted}

    cases = load_cases(args.cases)
    cases_by_id = {c["case_id"]: c for c in cases}
    profiles = load_profiles(args.profiles)
    jcfg = JudgeConfig.from_toml(args.judge_config)

    for cid, cfg in all_cfgs.items():
        if args.workers:
            cfg.max_workers = args.workers
        print(f"=== Running ablation config: {cid} ({cfg.description}) ===")
        summary = run_suite(
            cfg=cfg,
            cases=cases,
            profiles=profiles,
            out_root=args.out_root,
            cache_dir=args.cache_dir,
            reset_memory=args.reset_memory,
            resume=not args.no_resume,
        )
        print(
            f"[{cid}] {summary['ok_cases']} ok / {summary['failed_cases']} failed"
        )
        if args.judge:
            scores = judge_run(
                run_dir=Path(args.out_root) / cid,
                cases_by_id=cases_by_id,
                profiles=profiles,
                judge_cfg=jcfg,
                cache_dir=args.cache_dir,
                resume=not args.no_resume,
            )
            print(f"[{cid}] Judged {len(scores)} messages.")


def cmd_judge(args: argparse.Namespace) -> None:
    cases = load_cases(args.cases)
    cases_by_id = {c["case_id"]: c for c in cases}
    profiles = load_profiles(args.profiles)
    jcfg = JudgeConfig.from_toml(args.judge_config)
    out_root = Path(args.out_root)

    if args.all:
        run_dirs = sorted([d for d in out_root.iterdir() if d.is_dir() and (d / "outputs.jsonl").exists()])
    else:
        run_dirs = [out_root / args.run_id]

    for rdir in run_dirs:
        scores = judge_run(
            run_dir=rdir,
            cases_by_id=cases_by_id,
            profiles=profiles,
            judge_cfg=jcfg,
            cache_dir=args.cache_dir,
            resume=not args.no_resume,
        )
        print(f"[{rdir.name}] Judged {len(scores)} non-null messages -> {rdir / 'judge_scores.jsonl'}")


def cmd_human_sheet(args: argparse.Namespace) -> None:
    cases = load_cases(args.cases)
    cases_by_id = {c["case_id"]: c for c in cases}
    profiles = load_profiles(args.profiles)
    res = export_human_sheet(
        run_dir=Path(args.out_root) / args.run_id,
        cases_by_id=cases_by_id,
        profiles=profiles,
        out_dir=Path(args.out_root) / args.run_id / "human_eval",
        max_items=args.max_items,
    )
    print("Exported blind human rating sheet:", json.dumps(res, indent=2))


def cmd_analyze(args: argparse.Namespace) -> None:
    cases = load_cases(args.cases)
    cases_by_id = {c["case_id"]: c for c in cases}
    out_root = Path(args.out_root)

    all_metrics = {}
    if out_root.exists():
        for rdir in sorted(out_root.iterdir()):
            if rdir.is_dir() and (rdir / "outputs.jsonl").exists():
                all_metrics[rdir.name] = compute_run_metrics(rdir, cases_by_id)

    h_vs_l = compute_human_vs_llm(
        judge_scores_path=out_root / "full" / "judge_scores.jsonl",
        human_ratings_path=out_root / "full" / "human_eval" / "human_ratings.json",
    )

    summary_path = out_root / "summary_metrics.json"
    # Strip raw value lists for a compact summary JSON while keeping stats
    compact = {}
    for k, m in all_metrics.items():
        cm = dict(m)
        for subk in ("context_awareness", "goal_alignment", "clarity", "judge_mean", "latency_s", "llm_calls", "tool_calls", "total_tokens"):
            if isinstance(cm.get(subk), dict):
                cm[subk] = {sk: sv for sk, sv in cm[subk].items() if sk != "values"}
        compact[k] = cm

    summary_path.write_text(
        json.dumps({"configs": compact, "human_vs_llm": h_vs_l}, indent=2),
        encoding="utf-8",
    )
    # Paired comparisons always use identical IDs, including legacy 10-case runs.
    matched = {}
    reference_ids = set(all_metrics.get("full", {}).get("case_ids", []))
    for cid, metrics in all_metrics.items():
        if cid == "full":
            continue
        common = reference_ids & set(metrics.get("case_ids", []))
        if common:
            matched[cid] = {
                "case_ids": sorted(common),
                "full": compute_run_metrics(out_root / "full", cases_by_id, common),
                "variant": compute_run_metrics(out_root / cid, cases_by_id, common),
                "interpretation": "Descriptive only for legacy runs: model and judge confounds remain.",
            }
    (out_root / "matched_comparisons.json").write_text(json.dumps(matched, indent=2), encoding="utf-8")

    figs = generate_all_plots(all_metrics, h_vs_l, fig_dir=args.fig_dir)
    tbls = generate_all_tables(all_metrics, h_vs_l, table_dir=args.table_dir)
    print(f"Saved summary metrics to {summary_path}")
    print(f"Generated {len(figs)} figures: {figs}")
    print(f"Generated {len(tbls)} LaTeX tables: {tbls}")


def cmd_reset_memory(args: argparse.Namespace) -> None:
    out_root = Path(args.out_root)
    if args.run_id:
        targets = [out_root / args.run_id / "memory"]
    else:
        targets = list(out_root.glob("*/memory"))
    removed = 0
    for t in targets:
        if t.exists():
            shutil.rmtree(t)
            removed += 1
    print(f"Reset {removed} memory directories under {out_root}/")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="asl", description="Multi-Agent StudentLife Stress Coach CLI")
    sub = p.add_subparsers(dest="cmd", required=True)

    p_pre = sub.add_parser("preprocess", help="Preprocess raw StudentLife data into cache/features")
    p_pre.add_argument("--data-dir", default="data")
    p_pre.add_argument("--out-dir", default="cache/features")
    p_pre.set_defaults(func=cmd_preprocess)

    p_cases = sub.add_parser("cases", help="Generate deterministic cases and simulated profiles")
    p_cases.add_argument("--cache-dir", default="cache/features")
    p_cases.add_argument("--out-dir", default="cases")
    p_cases.set_defaults(func=cmd_cases)

    p_run = sub.add_parser("run", help="Run evaluation cases for a single configuration")
    p_run.add_argument("--config", default="configs/full.toml")
    p_run.add_argument("--run-id", default=None)
    p_run.add_argument("--cases", default="cases/cases.jsonl")
    p_run.add_argument("--profiles", default="cases/profiles.json")
    p_run.add_argument("--out-root", default="runs_corrected")
    p_run.add_argument("--cache-dir", default="cache/features")
    p_run.add_argument("--workers", type=int, default=None)
    p_run.add_argument("--reset-memory", action="store_true")
    p_run.add_argument("--no-resume", action="store_true")
    p_run.add_argument("--judge", action="store_true")
    p_run.add_argument("--judge-config", default="configs/judge.toml")
    p_run.set_defaults(func=cmd_run)

    p_abl = sub.add_parser("ablate", help="Run the ablation suite")
    p_abl.add_argument("--config", default="configs/ablations.toml")
    p_abl.add_argument("--only", default=None, help="Comma-separated config IDs to run")
    p_abl.add_argument("--cases", default="cases/cases.jsonl")
    p_abl.add_argument("--profiles", default="cases/profiles.json")
    p_abl.add_argument("--out-root", default="runs_corrected")
    p_abl.add_argument("--cache-dir", default="cache/features")
    p_abl.add_argument("--workers", type=int, default=None)
    p_abl.add_argument("--reset-memory", action="store_true")
    p_abl.add_argument("--no-resume", action="store_true")
    p_abl.add_argument("--judge", action="store_true")
    p_abl.add_argument("--judge-config", default="configs/judge.toml")
    p_abl.set_defaults(func=cmd_ablate)

    p_jdg = sub.add_parser("judge", help="Score non-null coaching messages with the LLM Judge")
    p_jdg.add_argument("--run-id", default="full")
    p_jdg.add_argument("--all", action="store_true")
    p_jdg.add_argument("--cases", default="cases/cases.jsonl")
    p_jdg.add_argument("--profiles", default="cases/profiles.json")
    p_jdg.add_argument("--out-root", default="runs_corrected")
    p_jdg.add_argument("--cache-dir", default="cache/features")
    p_jdg.add_argument("--judge-config", default="configs/judge.toml")
    p_jdg.add_argument("--no-resume", action="store_true")
    p_jdg.set_defaults(func=cmd_judge)

    p_hum = sub.add_parser("human-sheet", help="Export blind human evaluation sheet")
    p_hum.add_argument("--run-id", default="full")
    p_hum.add_argument("--cases", default="cases/cases.jsonl")
    p_hum.add_argument("--profiles", default="cases/profiles.json")
    p_hum.add_argument("--out-root", default="runs_corrected")
    p_hum.add_argument("--max-items", type=int, default=15)
    p_hum.set_defaults(func=cmd_human_sheet)

    p_ana = sub.add_parser("analyze", help="Compute metrics, figures, and LaTeX tables")
    p_ana.add_argument("--cases", default="cases/cases.jsonl")
    p_ana.add_argument("--out-root", default="runs_corrected")
    p_ana.add_argument("--fig-dir", default="report/figures")
    p_ana.add_argument("--table-dir", default="report/tables")
    p_ana.set_defaults(func=cmd_analyze)

    p_rst = sub.add_parser("reset-memory", help="Reset stored episode/preference memory")
    p_rst.add_argument("--run-id", default=None)
    p_rst.add_argument("--out-root", default="runs_corrected")
    p_rst.set_defaults(func=cmd_reset_memory)

    return p


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()

