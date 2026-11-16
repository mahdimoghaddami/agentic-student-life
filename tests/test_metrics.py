import json
from pathlib import Path
import tempfile
import unittest
from agentic_student_life.eval.metrics import compute_run_metrics


class MetricsTests(unittest.TestCase):
    def test_matched_cohorts_drop_unmatched_and_stale_judgments(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)
            records = [{"case_id": str(i), "status": "ok", "decision": "suggest",
                        "expected_decision": ["suggest"], "final_message": f"Message {i}",
                        "trace": {"latency_s": 10 * i}} for i in (1, 2)]
            scores = [{"case_id": str(i), "final_message": f"Message {i}" if i == 1 else "old text",
                       "judge_model": "fixed", "context_awareness": 4, "goal_alignment": 4,
                       "clarity": 4, "mean_score": 4} for i in (1, 2)]
            (p / "outputs.jsonl").write_text("\n".join(map(json.dumps, records)))
            (p / "judge_scores.jsonl").write_text("\n".join(map(json.dumps, scores)))
            metrics = compute_run_metrics(p, {}, {"1"})
            self.assertEqual(metrics["n_cases"], 1)
            self.assertEqual(metrics["latency_s"]["mean"], 10)
            self.assertEqual(metrics["n_judged"], 1)
            self.assertEqual(compute_run_metrics(p, {})["n_judged"], 1)
            self.assertIsNone(metrics["pref_adherence_rate"])
            self.assertEqual(metrics["pref_adherence_n"], 0)


if __name__ == "__main__":
    unittest.main()
