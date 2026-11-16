import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from agentic_student_life.config import RunConfig
from agentic_student_life.memory.store import MemoryStore
from agentic_student_life.orchestrator import run_suite


def record(store, cid, date, prefs=None, uid="u00"):
    return store.record_episode(uid=uid, case_id=cid, decision_time=date, decision="suggest",
                                skill_used=None, final_message="Break", feedback=None,
                                new_preferences=prefs or [])


class MemoryTests(unittest.TestCase):
    def test_snapshot_and_recall_exclude_future_and_current_feedback(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = MemoryStore(tmp, {})
            record(store, "later", "2013-04-29T20:00:00-04:00", ["future"])
            record(store, "earlier", "2013-04-10T20:00:00-04:00", ["past"])
            record(store, "current", "2013-04-12T20:00:00-04:00", ["current"])
            kw = {"decision_time": "2013-04-12T20:00:00-04:00"}
            snap = store.get_snapshot("u00", **kw)
            self.assertEqual([e["case_id"] for e in snap["recent_episodes"]], ["earlier"])
            self.assertEqual([p["preference"] for p in snap["learned_preferences"]], ["past"])
            self.assertEqual(store.make_recall_tool("u00", **kw)()["recent_episodes"],
                             snap["recent_episodes"])
            self.assertNotIn("future", store.format_for_prompt("u00", **kw))

    def test_atomic_updates_and_replacement(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = MemoryStore(tmp, {})
            with ThreadPoolExecutor(max_workers=8) as pool:
                list(pool.map(lambda i: record(store, str(i), "2013-04-10T20:00:00-04:00",
                                              [f"pref {i}"]), range(30)))
            self.assertEqual(len(store.load("u00")["episodes"]), 30)
            self.assertEqual(len(store.load("u00")["learned_preferences"]), 30)
            record(store, "0", "2013-04-10T20:00:00-04:00", ["replacement"])
            self.assertNotIn("pref 0", [p["preference"] for p in store.load("u00")["learned_preferences"]])

    def test_suite_orders_by_participant_and_rebuilds_resume_memory(self):
        cases = [
            {"case_id": "later", "participant_id": "u00", "decision_time": "2013-04-29T20:00:00-04:00"},
            {"case_id": "earlier", "participant_id": "u00", "decision_time": "2013-04-12T20:00:00-04:00"},
        ]
        seen = []
        def fake_case(**kw):
            c, store = kw["case"], kw["memory_store"]
            snap = store.get_snapshot(c["participant_id"], decision_time=c["decision_time"])
            seen.append((c["case_id"], [e["case_id"] for e in snap["recent_episodes"]]))
            record(store, c["case_id"], c["decision_time"], [c["case_id"]])
            return {**c, "status": "ok", "error": None, "decision": "suggest", "expected_decision": ["suggest"],
                    "memory_updates": [c["case_id"]], "final_message": "Break",
                    "trace": {"latency_s": 0, "total_tokens": 0}}
        with (
            tempfile.TemporaryDirectory() as tmp,
            patch("agentic_student_life.orchestrator.DataStore"),
            patch("agentic_student_life.orchestrator.LLMClient"),
            patch("agentic_student_life.orchestrator.run_case", side_effect=fake_case),
        ):
            cfg = RunConfig()
            run_suite(cfg=cfg, cases=cases, profiles={}, out_root=tmp, resume=False)
            self.assertEqual(seen, [("earlier", []), ("later", ["earlier"])])
            # Simulate an interrupted suite with only the earlier output saved.
            p = Path(tmp) / "full/outputs.jsonl"
            recs = [json.loads(line) for line in p.read_text().splitlines()]
            p.write_text(json.dumps(next(r for r in recs if r["case_id"] == "earlier")) + "\n")
            seen.clear()
            run_suite(cfg=cfg, cases=cases, profiles={}, out_root=tmp, resume=True)
            self.assertEqual(seen, [("later", ["earlier"])])


if __name__ == "__main__":
    unittest.main()
