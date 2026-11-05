"""Resume only histories affected by transient plan3 failures, preserving attempt 1."""
import copy
from datetime import datetime
import json
from pathlib import Path
import re
import shutil

from agentic_student_life.config import load_run_config
from agentic_student_life.orchestrator import run_suite

ROOT = Path("runs_corrected/2026-11-04_v3")


def lines(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def main():
    run = ROOT / "plan3"
    info_path = run / "recovery_info.json"
    if info_path.exists():
        print("Plan3 recovery already completed; no API calls needed.")
        return
    original_path = run / "attempt1_outputs.jsonl"
    if not original_path.exists():
        shutil.copy2(run / "outputs.jsonl", original_path)
        shutil.copy2(run / "failed_cases.json", run / "attempt1_failed_cases.json")
    original = {r["case_id"]: r for r in lines(original_path)}
    failed = [r for r in original.values() if r["status"] != "ok"]
    assert failed and all("504" in r["error"] and "DEADLINE_EXCEEDED" in r["error"] for r in failed)
    earliest = {}
    for r in failed:
        uid, time = r["participant_id"], r["decision_time"]
        earliest[uid] = min(time, earliest.get(uid, time))
    affected = sorted(cid for cid, r in original.items()
                      if r["participant_id"] in earliest
                      and r["decision_time"] >= earliest[r["participant_id"]])
    cases = lines(ROOT / "inputs/cases.jsonl")
    profiles = json.loads((ROOT / "inputs/profiles.json").read_text())
    print("Replaying only affected chronological suffixes:", affected, flush=True)
    result = run_suite(cfg=load_run_config("configs/2026-11-04/plan3.toml"),
                       cases=cases, profiles=profiles, out_root=ROOT,
                       cache_dir="cache/features", resume=True, reset_memory=False)
    if result["failed_cases"]:
        raise RuntimeError("Recovery still has failures; stopping without further calls")
    final = {r["case_id"]: r for r in lines(run / "outputs.jsonl")}
    for cid in original.keys() - set(affected):
        assert original[cid] == final[cid], cid
    starts, finishes = {}, {}
    pattern = re.compile(r"^(.*?) \[INFO\] (Starting|Finished) case (case_\d+)")
    for line in (run / "run.log").read_text().splitlines():
        match = pattern.match(line)
        if match:
            stamp, action, cid = match.groups()
            value = datetime.strptime(stamp, "%Y-%m-%d %H:%M:%S,%f")
            if action == "Starting":
                starts.setdefault(cid, value)
            else:
                finishes[cid] = value
    overrides = {}
    for cid in affected:
        old, new = original[cid]["trace"], final[cid]["trace"]
        trace = copy.deepcopy(new)
        for key in ["llm_calls", "tool_calls", "prompt_tokens", "completion_tokens", "total_tokens"]:
            trace[key] += old[key]
        trace["models_used"] = sorted(set(old["models_used"]) | set(new["models_used"]))
        trace["per_agent"] = {}
        for agent in old["per_agent"].keys() | new["per_agent"].keys():
            trace["per_agent"][agent] = {
                key: old["per_agent"].get(agent, {}).get(key, 0) + new["per_agent"].get(agent, {}).get(key, 0)
                for key in ["calls", "tokens"]}
        trace["active_attempt_latency_s"] = old["latency_s"] + new["latency_s"]
        trace["latency_s"] = round((finishes[cid] - starts[cid]).total_seconds(), 3)
        overrides[cid] = trace
    info = {"reason": "Transient provider HTTP 504; generation code and settings unchanged",
            "initial_failed_case_ids": [r["case_id"] for r in failed],
            "replayed_case_ids": affected,
            "reused_case_ids": sorted(original.keys() - set(affected)),
            "original_outputs": original_path.name,
            "trace_overrides_for_analysis": overrides,
            "latency_note": "Derived latency spans the first case start through the final valid output, including outer recovery waits. Calls and tokens sum recorded completed steps across both attempts. Raw final output traces remain unchanged; planning/reflection round budgets refer to the final attempt."}
    info_path.write_text(json.dumps(info, indent=2) + "\n")
    print(json.dumps({"recovered": affected, "reused": len(original)-len(affected)}), flush=True)


if __name__ == "__main__":
    main()
