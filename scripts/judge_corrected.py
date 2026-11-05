"""Judge saved corrected outputs without regenerating coach messages.

Uses the existing rubric, fingerprints and resume logic, with an explicit
OpenAI transport and a shared $2 usage ledger for the experiment.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import time
from types import SimpleNamespace
import urllib.error
import urllib.request

from dotenv import load_dotenv

from agentic_student_life.budget import UsageBudget
from agentic_student_life.config import JudgeConfig
from agentic_student_life.eval import judge


class OpenAIJudge:
    def __init__(self, budget):
        self.key = os.environ["OPENAI_API_KEY"]
        self.generate = budget.wrap(self._generate, "OPENAI_API_KEY")

    def _generate(self, **payload):
        request = urllib.request.Request(
            "https://api.openai.com/v1/chat/completions",
            data=json.dumps(payload).encode(),
            headers={"Authorization": f"Bearer {self.key}",
                     "Content-Type": "application/json"},
        )
        with urllib.request.urlopen(request, timeout=90) as response:
            data = json.load(response)
        usage = data["usage"]
        return SimpleNamespace(data=data, usage_metadata=SimpleNamespace(
            prompt_token_count=usage["prompt_tokens"],
            candidates_token_count=usage["completion_tokens"],
            total_token_count=usage["total_tokens"],
        ))

    def complete_json(self, *, agent, model, system, user, schema, tracker, temperature):
        shape = schema.model_json_schema()
        shape["additionalProperties"] = False
        payload = dict(
            model=model.removeprefix("openai:"),
            messages=[{"role": "system", "content": system},
                      {"role": "user", "content": user}],
            reasoning_effort="none", temperature=temperature,
            max_completion_tokens=2048,
            response_format={"type": "json_schema", "json_schema": {
                "name": "coach_evaluation", "strict": True, "schema": shape}},
        )
        start = time.perf_counter()
        for attempt in range(3):
            try:
                response = self.generate(**payload)
                break
            except urllib.error.HTTPError as exc:
                if exc.code in (429, 500, 502, 503, 504) and attempt < 2:
                    time.sleep(6 * (attempt + 1))
                    continue
                detail = exc.read().decode(errors="replace").replace(self.key, "[REDACTED]")
                raise RuntimeError(f"OpenAI HTTP {exc.code}: {detail}") from None
        data = response.data
        if data["model"] != payload["model"]:
            raise ValueError("OpenAI returned a different model snapshot")
        choice = data["choices"][0]
        if choice["finish_reason"] != "stop" or choice["message"].get("refusal"):
            raise ValueError("Judge did not return a complete evaluation")
        content = choice["message"]["content"]
        result = schema.model_validate_json(content)
        usage = data["usage"]
        tracker.record_llm(
            agent=agent, model=model, turns=1,
            prompt_tokens=usage["prompt_tokens"],
            completion_tokens=usage["completion_tokens"],
            total_tokens=usage["total_tokens"],
            latency_s=time.perf_counter() - start,
            prompt_preview="", response_preview="",
        )
        return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default="runs_corrected/2026-11-04_v3")
    parser.add_argument("--runs", nargs="+", default=["full"])
    args = parser.parse_args()
    root = Path(args.root)
    load_dotenv()
    if not os.environ.get("OPENAI_API_KEY"):
        raise ValueError("OPENAI_API_KEY is required")
    cfg = JudgeConfig.from_toml("configs/2026-11-04/judge.toml")
    budget = UsageBudget(root / "judge_api_usage.jsonl", limit_usd=2,
                         input_per_million=.75, output_per_million=4.5,
                         max_output_tokens=2048)
    # Inject only the evaluation transport; generation code remains frozen.
    judge.LLMClient = lambda: OpenAIJudge(budget)
    cases = {c["case_id"]: c for c in map(json.loads, (root / "inputs/cases.jsonl").read_text().splitlines())}
    profiles = json.loads((root / "inputs/profiles.json").read_text())
    for name in args.runs:
        scores = judge.judge_run(run_dir=root / name, cases_by_id=cases,
                                 profiles=profiles, judge_cfg=cfg, resume=True)
        print(f"{name}: {len(scores)} saved evaluations; shared cost estimate ${budget.spent:.6f}", flush=True)


if __name__ == "__main__":
    main()
