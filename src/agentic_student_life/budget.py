"""Thread-safe Gemini usage accounting with conservative per-request reservations."""
import json
from pathlib import Path
import threading
import time


class UsageBudget:
    def __init__(self, path, *, limit_usd, input_per_million, output_per_million,
                 max_output_tokens=8192):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.limit = limit_usd
        self.input_rate = input_per_million
        self.output_rate = output_per_million
        self.max_output_tokens = max_output_tokens
        self.spent = self.reserved = 0.0
        self.lock = threading.Lock()
        if self.path.exists():
            for line in self.path.read_text(encoding="utf-8").splitlines():
                self.spent += json.loads(line).get("estimated_cost_usd", 0)

    def wrap(self, generate, credential):
        def tracked(*args, **kwargs):
            # Each selected Gemini model has a 1,048,576-token input limit.
            reserve = (1_048_576 * self.input_rate +
                       self.max_output_tokens * self.output_rate) / 1_000_000
            with self.lock:
                if self.spent + self.reserved + reserve > self.limit:
                    raise RuntimeError("Configured API spending guard reached; no request sent.")
                self.reserved += reserve
            start = time.perf_counter()
            try:
                result = generate(*args, **kwargs)
            except Exception as exc:
                code = getattr(exc, "code", None)
                # A client-side rejection has no generated output. A network/server
                # failure is conservatively charged at the reserved upper bound.
                known_rejection = isinstance(code, int) and 400 <= code < 500
                rec = {"status": "rejected" if known_rejection else "uncertain",
                       "credential": credential, "model": kwargs.get("model"),
                       "error_type": type(exc).__name__, "http_status": code,
                       "estimated_cost_usd": 0 if known_rejection else reserve,
                       "conservative_upper_bound": not known_rejection}
                self._finish(rec, reserve, start)
                raise
            usage = result.usage_metadata
            prompt = getattr(usage, "prompt_token_count", 0) or 0
            candidates = getattr(usage, "candidates_token_count", 0) or 0
            thoughts = getattr(usage, "thoughts_token_count", 0) or 0
            total = getattr(usage, "total_token_count", 0) or 0
            output = max(total - prompt, candidates + thoughts)
            cost = (prompt * self.input_rate + output * self.output_rate) / 1_000_000
            self._finish({"status": "ok", "credential": credential, "model": kwargs.get("model"),
                          "prompt_tokens": prompt, "candidate_tokens": candidates,
                          "thinking_tokens": thoughts, "billable_output_tokens": output,
                          "total_tokens": total, "estimated_cost_usd": cost}, reserve, start)
            return result
        return tracked

    def _finish(self, rec, reserve, start):
        with self.lock:
            self.reserved -= reserve
            self.spent += rec["estimated_cost_usd"]
            rec["cumulative_estimated_cost_usd"] = self.spent
            rec["latency_s"] = round(time.perf_counter() - start, 3)
            with self.path.open("a", encoding="utf-8") as stream:
                stream.write(json.dumps(rec) + "\n")
