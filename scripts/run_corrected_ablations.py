"""Run only the eight missing required variants, reusing the saved full baseline."""
import copy
import argparse
import json
from pathlib import Path
import tomllib

from agentic_student_life.config import RunConfig
from agentic_student_life.orchestrator import run_suite
from agentic_student_life.provenance import source_digest

ROOT = Path("runs_corrected/2026-11-04_v3")
VARIANTS = {
    "single": {"system": {"mode": "single_agent"}},
    "no_refl": {"reflection": {"enabled": False, "max_rounds": 0}},
    "no_plan": {"planning": {"enabled": False, "max_rounds": 0}},
    "refl1": {"reflection": {"max_rounds": 1}},
    "refl3": {"reflection": {"max_rounds": 3}},
    "plan1": {"planning": {"max_rounds": 1}},
    "plan3": {"planning": {"max_rounds": 3}},
    "modelB": {"system": {"model": "gemini:gemini-3.5-flash-lite",
                           "input_usd_per_million": .30,
                           "output_usd_per_million": 2.50}},
}


def google_guard_total():
    return sum(json.loads(line).get("estimated_cost_usd", 0)
               for path in ROOT.rglob("api_usage.jsonl")
               for line in path.read_text().splitlines() if line.strip())


def main(only=None):
    with open("configs/2026-11-04/full-paid.toml", "rb") as stream:
        base = tomllib.load(stream)
    baseline = json.loads((ROOT / "full/manifest.json").read_text())
    if source_digest() != baseline["source_digest"]:
        raise ValueError("Generation source changed since full baseline; review required")
    cases = [json.loads(line) for line in (ROOT / "inputs/cases.jsonl").read_text().splitlines()]
    profiles = json.loads((ROOT / "inputs/profiles.json").read_text())
    for name, changes in VARIANTS.items():
        if only and name not in only:
            continue
        config_path = Path("configs/2026-11-04") / f"{name}.toml"
        # Persist the exact initial spending allocation for deterministic resume.
        if config_path.exists():
            with config_path.open("rb") as stream:
                cfg = RunConfig.from_dict(tomllib.load(stream))
        else:
            remaining = 20 - google_guard_total()
            if remaining <= .1:
                raise RuntimeError("Shared $20 Google spending guard reached")
            data = copy.deepcopy(base)
            for section, values in changes.items():
                data[section].update(values)
            data["system"].update(config_id=name, description=f"Corrected controlled variant: {name}",
                                  budget_usd=remaining)
            cfg = RunConfig.from_dict(data)
            config_path.write_text(cfg.to_toml())
        print(f"Starting/resuming {name}; full baseline will not run", flush=True)
        result = run_suite(cfg=cfg, cases=cases, profiles=profiles,
                           out_root=str(ROOT), cache_dir="cache/features",
                           reset_memory=False, resume=True)
        print(json.dumps(result), flush=True)
        if result["failed_cases"]:
            raise RuntimeError(f"{name} has failures; stopping to review before more API calls")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--only", nargs="+", choices=list(VARIANTS))
    main(parser.parse_args().only)
