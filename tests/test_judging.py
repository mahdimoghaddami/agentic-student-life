import json
from pathlib import Path
import tempfile
from unittest.mock import patch
import unittest

from agentic_student_life.config import JudgeConfig
from agentic_student_life.eval.context import evaluation_payload
from agentic_student_life.eval.human import export_human_sheet
from agentic_student_life.eval.judge import JudgeOutput, judge_run, judge_single_record


def sample(i=0):
    return {"case_id": f"case_{i}", "config_id": "test", "participant_id": "u00",
            "decision_time": "2013-04-12T20:00:00-04:00", "status": "ok",
            "decision": "suggest", "final_message": "Take a quiet break.",
            "evaluation_context": {"observations": {"sleep": 5},
                                   "simulated_profile": {"goals": ["Rest"]}}}


class FakeJudge:
    def __init__(self):
        self.prompts = []

    def complete_json(self, **kw):
        self.prompts.append(kw["user"])
        kw["tracker"].models_used.add(kw["model"])
        return JudgeOutput(context_awareness=4, goal_alignment=4, clarity=4,
                           decision_appropriate=True, justification="Grounded.")


class JudgingTests(unittest.TestCase):
    def test_no_labels_rationale_or_current_feedback_reach_judge(self):
        llm = FakeJudge()
        judge_single_record(rec=sample(), case={"expected_decision": ["none"],
                            "rationale": "SECRET LABEL", "scripted_feedback": "FUTURE FEEDBACK"},
                            profile={"goals": ["wrong profile"]}, llm=llm, judge_cfg=JudgeConfig())
        self.assertEqual(json.loads(llm.prompts[0]), evaluation_payload(sample()))
        self.assertNotIn("SECRET LABEL", llm.prompts[0])
        self.assertNotIn("FUTURE FEEDBACK", llm.prompts[0])

    def test_resume_invalidates_changed_messages_and_judge_model(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "outputs.jsonl"
            p.write_text(json.dumps(sample()) + "\n")
            llm = FakeJudge()
            with patch("agentic_student_life.eval.judge.LLMClient", return_value=llm):
                cfg = JudgeConfig()
                def run():
                    return judge_run(run_dir=tmp, cases_by_id={}, profiles={}, judge_cfg=cfg)
                run()
                run()
                self.assertEqual(len(llm.prompts), 1)
                changed = sample()
                changed["final_message"] = "A different message."
                p.write_text(json.dumps(changed) + "\n")
                run()
                cfg.model = "gemini:different-judge"
                run()
                self.assertEqual(len(llm.prompts), 3)

    def test_human_sheet_contains_same_context_and_full_rubric(self):
        with tempfile.TemporaryDirectory() as tmp:
            records = [sample(i) for i in range(10)]
            (Path(tmp) / "outputs.jsonl").write_text("\n".join(map(json.dumps, records)))
            result = export_human_sheet(run_dir=tmp, cases_by_id={}, profiles={}, out_dir=Path(tmp)/"human")
            text = Path(result["html_path"]).read_text(encoding="utf-8")
            self.assertIn("3 (Adequate)", text)
            self.assertIn("learned feedback", text)
            self.assertNotIn("mean_score", text)
            import csv
            with open(result["csv_path"], encoding="utf-8", newline="") as f:
                row = next(csv.DictReader(f))
            self.assertEqual(json.loads(row["evaluation_context"]), evaluation_payload(records[0]))


if __name__ == "__main__":
    unittest.main()
