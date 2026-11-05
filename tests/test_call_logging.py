"""Call traces from concurrent cases must remain one valid JSON record per line."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
import json
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from agentic_student_life.llm import CallTracker


class CallLoggingTests(unittest.TestCase):
    def test_concurrent_trackers_serialize_append_and_keep_every_record(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "calls.jsonl"
            original_open = Path.open
            state_lock = threading.Lock()
            state = {"active": 0, "peak": 0}
            start = threading.Barrier(8)

            @contextmanager
            def observed_open(candidate, *args, **kwargs):
                with original_open(candidate, *args, **kwargs) as stream:
                    with state_lock:
                        state["active"] += 1
                        state["peak"] = max(state["peak"], state["active"])
                    # Expose overlapping file handles deterministically on every platform.
                    time.sleep(0.001)
                    try:
                        yield stream
                    finally:
                        with state_lock:
                            state["active"] -= 1

            def write_case(index):
                tracker = CallTracker(f"case_{index}", "full", calls_log_path=path)
                start.wait(timeout=10)
                for turn in range(12):
                    tracker.record_llm(
                        agent="analyst", model="gemini:test", turns=1,
                        prompt_tokens=10, completion_tokens=5, total_tokens=15,
                        latency_s=0.01, prompt_preview=f"turn {turn}",
                        response_preview='A response with "quotes" and a newline\n.' * 5,
                    )

            with patch.object(Path, "open", new=observed_open):
                with ThreadPoolExecutor(max_workers=8) as pool:
                    list(pool.map(write_case, range(8)))
            self.assertEqual(state["peak"], 1, "Concurrent trackers opened the same append log together")
            records = [json.loads(line) for line in path.read_text().splitlines()]
            self.assertEqual(len(records), 96)
            for index in range(8):
                self.assertEqual(sum(r["case_id"] == f"case_{index}" for r in records), 12)


if __name__ == "__main__":
    unittest.main()
