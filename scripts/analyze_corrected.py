"""Validate and summarize the completed corrected suite, without API calls."""
import csv
import hashlib
import json
from pathlib import Path
from datetime import datetime
import tomllib

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from agentic_student_life.config import JudgeConfig
from agentic_student_life.eval.context import message_fingerprint
from agentic_student_life.eval.human import compute_human_vs_llm
from agentic_student_life.eval.judge import score_fingerprint
from agentic_student_life.eval.latex import generate_all_tables
from agentic_student_life.eval.metrics import compute_run_metrics, _mean_std
from agentic_student_life.eval.plots import generate_all_plots

ROOT = Path("runs_corrected/2026-11-04_v3")
NAMES = ["full", "single", "no_refl", "no_plan", "refl1", "refl3", "plan1", "plan3", "modelB"]


def load_lines(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def main():
    cases = {c["case_id"]: c for c in load_lines(ROOT / "inputs/cases.jsonl")}
    cfg = JudgeConfig.from_toml("configs/2026-11-04/judge.toml")
    for relative, checksum in json.loads((ROOT / "baseline_preservation_sha256.json").read_text()).items():
        assert hashlib.sha256((ROOT / relative).read_bytes()).hexdigest() == checksum, relative
    for relative, checksum in json.loads((ROOT / "legacy_runs_sha256.json").read_text()).items():
        assert hashlib.sha256((Path("runs") / relative).read_bytes()).hexdigest() == checksum, relative
    all_metrics, records, scores = {}, {}, {}
    for name in NAMES:
        output_rows = load_lines(ROOT / name / "outputs.jsonl")
        assert len(output_rows) == len(cases), name
        records[name] = {r["case_id"]: r for r in output_rows}
        assert set(records[name]) == set(cases), name
        assert all(r["status"] == "ok" for r in records[name].values()), name
        snapshot = tomllib.loads((ROOT / name / "config.snapshot.toml").read_text())
        manifest = json.loads((ROOT / name / "manifest.json").read_text())
        full_manifest = json.loads((ROOT / "full/manifest.json").read_text())
        assert manifest["source_digest"] == full_manifest["source_digest"], name
        assert manifest["data_digest"] == full_manifest["data_digest"], name
        for cid, record in records[name].items():
            assert record["participant_id"] == cases[cid]["participant_id"]
            assert record["decision_time"] == cases[cid]["decision_time"]
            assert bool(record["final_message"]) == (record["decision"] != "none")
            assert record["trace"]["models_used"] == [snapshot["system"]["model"]]
            assert record["planning"]["rounds_used"] <= snapshot["planning"]["max_rounds"]
            assert record["reflection"]["rounds_used"] <= snapshot["reflection"]["max_rounds"]
            for previous in record["evaluation_context"]["recent_interactions"]:
                assert datetime.fromisoformat(previous["decision_time"]) < datetime.fromisoformat(record["decision_time"])
        scores[name] = {r["case_id"]: r for r in load_lines(ROOT / name / "judge_scores.jsonl")}
        nonnull = {cid for cid, r in records[name].items() if r.get("final_message")}
        assert set(scores[name]) == nonnull, name
        for cid, score in scores[name].items():
            assert score["message_fingerprint"] == message_fingerprint(records[name][cid])
            assert score["evaluation_fingerprint"] == score_fingerprint(records[name][cid], cfg)
        all_metrics[name] = compute_run_metrics(ROOT / name, cases)
        recovery_path = ROOT / name / "recovery_info.json"
        if recovery_path.exists():
            recovery = json.loads(recovery_path.read_text())
            overrides = recovery["trace_overrides_for_analysis"]
            m = all_metrics[name]
            m["recovery"] = recovery
            m["initial_execution_success_rate"] = 100 * (
                len(cases) - len(recovery["initial_failed_case_ids"])) / len(cases)
            for field in ["latency_s", "llm_calls", "tool_calls", "total_tokens"]:
                values = [float(overrides.get(cid, r["trace"])[field]) for cid, r in records[name].items()]
                mean, std = _mean_std(values)
                m[field] = {"mean": mean, "std": std, "values": values}
            for category, cm in m["by_category"].items():
                group = [overrides.get(cid, r["trace"]) for cid, r in records[name].items()
                         if r["category"] == category]
                for key, field in [("latency_mean", "latency_s"), ("calls_mean", "llm_calls"), ("tokens_mean", "total_tokens")]:
                    cm[key] = _mean_std([r[field] for r in group])[0]
        all_metrics[name]["judge_decision_appropriate_pct_nonnull"] = (
            100 * sum(score["decision_appropriate"] for score in scores[name].values()) / len(scores[name])
            if scores[name] else None)
    human = compute_human_vs_llm(
        judge_scores_path=ROOT / "full/judge_scores.jsonl",
        human_ratings_path=ROOT / "full/human_eval/human_ratings.json",
    )
    assert human["n_paired"] == 10
    pairs = human["paired_items"]
    human["all_criterion_ratings_mad"] = sum(
        item["abs_diff"][criterion] for item in pairs
        for criterion in ("context_awareness", "goal_alignment", "clarity")) / (3 * len(pairs))
    human["note"] = "MAD of individual criterion ratings differs from MAD after averaging each message's three scores."
    # The legacy helper calls a <=0.34 tolerance 'exact' for mean scores.
    # Report literal equality here, without changing frozen generation source.
    human["by_criterion"]["mean"]["exact_agreement_rate"] = sum(
        item["human"]["mean"] == item["llm"]["mean"] for item in pairs) / len(pairs)
    comparisons = {}
    for name in NAMES[1:]:
        common = sorted(set(scores["full"]) & set(scores[name]))
        def mean(which, field):
            return sum(scores[which][cid][field] for cid in common) / len(common) if common else None
        comparisons[name] = {
            "case_ids": sorted(cases), "n_paired_decisions": len(cases),
            "decision_matches_full": sum(records[name][cid]["decision"] == records["full"][cid]["decision"] for cid in cases),
            "common_nonnull_case_ids": common, "n_paired_messages": len(common),
            "full_quality_on_common": mean("full", "mean_score"),
            "variant_quality_on_common": mean(name, "mean_score"),
            "paired_quality_difference_variant_minus_full": mean(name, "mean_score") - mean("full", "mean_score") if common else None,
            "interpretation": "Descriptive single-run comparisons on fixed cases; no statistical superiority claim.",
        }
    costs = {}
    for name in NAMES:
        usage = load_lines(ROOT / name / "api_usage.jsonl")
        assert all(x.get("total_tokens", 0) > 0 for x in usage if x["status"] == "ok"), name
        costs[name] = {
            "successful_response_estimate_usd": sum(x["estimated_cost_usd"] for x in usage if x["status"] == "ok"),
            "uncertain_failure_upper_bound_usd": sum(x["estimated_cost_usd"] for x in usage if x["status"] == "uncertain"),
            "successful_provider_requests": sum(x["status"] == "ok" for x in usage),
            "failed_provider_attempts": sum(x["status"] != "ok" for x in usage),
            "actual_prompt_tokens_successful_requests": sum(x.get("prompt_tokens", 0) for x in usage),
            "actual_total_tokens_successful_requests": sum(x.get("total_tokens", 0) for x in usage),
        }
    judge_usage = load_lines(ROOT / "judge_api_usage.jsonl")
    costs["judge"] = {"estimated_usd": sum(x["estimated_cost_usd"] for x in judge_usage),
                      "successful_requests": sum(x["status"] == "ok" for x in judge_usage)}
    data = {"configs": all_metrics, "human_vs_llm": human, "costs": costs,
            "efficiency_note": "Per-case trace calls/tokens cover completed model steps; retries that fail after intermediate tool responses can consume extra successful provider calls. Provider ledgers separately report all observed successful requests and failed attempts. Latency includes waits/retries; judge is excluded."}
    (ROOT / "summary_metrics.json").write_text(json.dumps(data, indent=2) + "\n")
    (ROOT / "matched_comparisons.json").write_text(json.dumps(comparisons, indent=2) + "\n")
    generate_all_plots(all_metrics, human, ROOT / "report/figures")
    generate_all_tables(all_metrics, human, ROOT / "report/tables")
    figure_dir = ROOT / "report/figures"
    labels = NAMES[1:]
    fig, ax = plt.subplots(figsize=(7, 3.2))
    differences = [comparisons[n]["paired_quality_difference_variant_minus_full"] for n in labels]
    ax.barh(labels, differences, color=["#0f766e" if x >= 0 else "#b45309" for x in differences])
    ax.axvline(0, color="#475569", linewidth=1)
    ax.set_xlabel("Variant minus full: quality on common non-null cases (1–5)")
    ax.invert_yaxis(); fig.tight_layout()
    fig.savefig(figure_dir / "fig5_paired_quality.pdf")
    fig.savefig(figure_dir / "fig5_paired_quality.png", dpi=160)
    plt.close(fig)
    fig, ax = plt.subplots(figsize=(7, 3))
    ax.bar(NAMES, [costs[n]["successful_response_estimate_usd"] for n in NAMES], label="Successful-response estimate")
    ax.bar(NAMES, [costs[n]["uncertain_failure_upper_bound_usd"] for n in NAMES],
           bottom=[costs[n]["successful_response_estimate_usd"] for n in NAMES],
           color="#cbd5e1", label="Uncertain failure upper bound (not confirmed charge)")
    ax.set_ylabel("USD"); ax.tick_params(axis="x", rotation=25)
    ax.legend(fontsize=7); fig.tight_layout()
    fig.savefig(figure_dir / "fig6_usage_cost.pdf")
    fig.savefig(figure_dir / "fig6_usage_cost.png", dpi=160)
    plt.close(fig)
    fig, ax = plt.subplots(figsize=(7, 3))
    depth_names = ["no_plan", "plan1", "full", "plan3", "no_refl", "refl1", "refl3"]
    x = list(range(len(depth_names)))
    ax.bar([v-.17 for v in x], [all_metrics[n]["planning_rounds_mean"] for n in depth_names], width=.34, label="Actual planner calls / case")
    ax.bar([v+.17 for v in x], [all_metrics[n]["reflection_rounds_mean"] for n in depth_names], width=.34, label="Actual critic cycles / message")
    ax.set_xticks(x, depth_names); ax.set_ylabel("Observed mean rounds")
    ax.legend(fontsize=8); fig.tight_layout()
    fig.savefig(figure_dir / "fig7_effective_rounds.pdf")
    fig.savefig(figure_dir / "fig7_effective_rounds.png", dpi=160)
    plt.close(fig)
    with (ROOT / "comparison.csv").open("w", newline="") as stream:
        fields = ["config", "cases", "ok", "decision_accuracy_pct", "preference_adherence_pct",
                  "messages_judged", "quality_mean", "latency_mean_s", "calls_mean", "tokens_mean",
                  "judge_appropriate_nonnull_pct"]
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for name, m in all_metrics.items():
            writer.writerow(dict(zip(fields, [name, m["n_cases"], m["n_ok"], m["decision_acc"],
                m["pref_adherence_rate"], m["n_judged"], m["judge_mean"]["mean"],
                m["latency_s"]["mean"], m["llm_calls"]["mean"], m["total_tokens"]["mean"],
                m["judge_decision_appropriate_pct_nonnull"]])))
    print((ROOT / "comparison.csv").read_text())
    print("Human criterion MAD:", human["all_criterion_ratings_mad"])
    print("Cost estimates:", json.dumps(costs, indent=2))


if __name__ == "__main__":
    main()
