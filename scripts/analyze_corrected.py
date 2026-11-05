"""Validate and summarize the completed corrected suite, without API calls."""
import csv
import hashlib
import json
from pathlib import Path

from agentic_student_life.config import JudgeConfig
from agentic_student_life.eval.context import message_fingerprint
from agentic_student_life.eval.human import compute_human_vs_llm
from agentic_student_life.eval.judge import score_fingerprint
from agentic_student_life.eval.latex import generate_all_tables
from agentic_student_life.eval.metrics import compute_run_metrics
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
        records[name] = {r["case_id"]: r for r in load_lines(ROOT / name / "outputs.jsonl")}
        assert set(records[name]) == set(cases), name
        assert all(r["status"] == "ok" for r in records[name].values()), name
        scores[name] = {r["case_id"]: r for r in load_lines(ROOT / name / "judge_scores.jsonl")}
        nonnull = {cid for cid, r in records[name].items() if r.get("final_message")}
        assert set(scores[name]) == nonnull, name
        for cid, score in scores[name].items():
            assert score["message_fingerprint"] == message_fingerprint(records[name][cid])
            assert score["evaluation_fingerprint"] == score_fingerprint(records[name][cid], cfg)
        all_metrics[name] = compute_run_metrics(ROOT / name, cases)
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
    with (ROOT / "comparison.csv").open("w", newline="") as stream:
        fields = ["config", "cases", "ok", "decision_accuracy_pct", "preference_adherence_pct",
                  "messages_judged", "quality_mean", "latency_mean_s", "calls_mean", "tokens_mean"]
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for name, m in all_metrics.items():
            writer.writerow(dict(zip(fields, [name, m["n_cases"], m["n_ok"], m["decision_acc"],
                m["pref_adherence_rate"], m["n_judged"], m["judge_mean"]["mean"],
                m["latency_s"]["mean"], m["llm_calls"]["mean"], m["total_tokens"]["mean"]])))
    print((ROOT / "comparison.csv").read_text())
    print("Human criterion MAD:", human["all_criterion_ratings_mad"])
    print("Cost estimates:", json.dumps(costs, indent=2))


if __name__ == "__main__":
    main()
