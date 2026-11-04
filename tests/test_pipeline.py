from contextlib import ExitStack
from types import SimpleNamespace as NS
import unittest
from unittest.mock import patch

from agentic_student_life.agents.schemas import AnalystOutput, PlannerOutput, WriterOutput
from agentic_student_life.agents.schemas import CriticOutput
from agentic_student_life.config import RunConfig
from agentic_student_life.orchestrator import run_case


class PipelineTests(unittest.TestCase):
    def execute(self, cfg, planner=None, writer=None, critic=None):
        analyst = AnalystOutput(stress_level_assessment="high", summary="Some stress")
        memory = NS(format_for_prompt=lambda *a, **kw: "",
                    get_snapshot=lambda *a, **kw: {}, record_episode=lambda **kw: [])
        prefix = "agentic_student_life.orchestrator."
        with ExitStack() as stack:
            for name, value in {
                "tool_map": lambda v: {"get_time_context": lambda: {}},
                "make_tools": lambda v: [], "evidence_summary": lambda v: {"sleep": 5},
                "run_analyst": lambda **kw: analyst,
                "run_memory_manager": lambda **kw: [],
            }.items():
                stack.enter_context(patch(prefix + name, new=value))
            p = stack.enter_context(patch(prefix + "run_planner_step", side_effect=planner))
            stack.enter_context(patch(prefix + "run_writer", side_effect=writer or (
                lambda **kw: WriterOutput(decision="suggest", skill_used="micro_study_break",
                                          final_message="Take a quiet break."))))
            stack.enter_context(patch(prefix + "run_critic", side_effect=critic))
            result = run_case(case={"case_id": "test", "participant_id": "u00",
                                   "decision_time": "2013-04-12T20:00:00-04:00"},
                              cfg=cfg, data_store=NS(get_view=lambda *a, **kw: None),
                              memory_store=memory, llm=None)
            return result, p.call_args_list

    def test_planning_budgets_are_real_call_limits_and_review_evidence(self):
        for budget in (1, 2, 3):
            with self.subTest(budget=budget):
                cfg = RunConfig()
                cfg.reflection.enabled = False
                cfg.planning.max_rounds = budget
                def planner(**kw):
                    return PlannerOutput(status="finalize" if kw["round_idx"] == budget else "gather_more",
                                         decision="suggest", plan_steps=["Check sleep"])
                result, calls = self.execute(cfg, planner=planner)
                self.assertEqual(result["status"], "ok", result.get("error"))
                self.assertEqual(len(calls), budget)
                self.assertEqual(result["planning"]["rounds_used"], budget)
                self.assertTrue(calls[-1].kwargs["analyst_reports"])

    def test_reflection_can_withhold_a_message_without_stale_decision_or_skill(self):
        cfg = RunConfig()
        cfg.planning.enabled = False
        drafts = iter([
            WriterOutput(decision="suggest", skill_used="micro_study_break", final_message="Break."),
            WriterOutput(decision="none", skill_used=None, final_message=None),
        ])
        result, _ = self.execute(
            cfg, writer=lambda **kw: next(drafts),
            critic=lambda **kw: CriticOutput(verdict="revise", critique="Avoid over-messaging."),
        )
        self.assertEqual(result["status"], "ok", result.get("error"))
        self.assertEqual(result["decision"], "none")
        self.assertIsNone(result["skill_used"])
        self.assertIsNone(result["final_message"])
        self.assertEqual(result["reflection"]["rounds_used"], 1)

    def test_reflection_updates_ask_decision_and_skill(self):
        cfg = RunConfig()
        cfg.planning.enabled = False
        cfg.reflection.max_rounds = 1
        drafts = iter([
            WriterOutput(decision="suggest", skill_used="micro_study_break", final_message="Break."),
            WriterOutput(decision="ask", skill_used="clarifying_question", final_message="How are you?"),
        ])
        result, _ = self.execute(
            cfg, writer=lambda **kw: next(drafts),
            critic=lambda **kw: CriticOutput(verdict="revise", critique="Missing data: ask instead."),
        )
        self.assertEqual((result["decision"], result["skill_used"], result["final_message"]),
                         ("ask", "clarifying_question", "How are you?"))

    def test_non_null_decision_requires_a_message(self):
        cfg = RunConfig()
        cfg.planning.enabled = False
        result, _ = self.execute(cfg, writer=lambda **kw: WriterOutput(decision="suggest"))
        self.assertEqual(result["status"], "failed")
        self.assertIn("non-empty", result["error"])


if __name__ == "__main__":
    unittest.main()
