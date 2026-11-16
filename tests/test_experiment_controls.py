import json
from pathlib import Path
import tempfile
from types import SimpleNamespace as NS
import unittest
from unittest.mock import Mock, PropertyMock, patch

from agentic_student_life.config import RunConfig, load_ablation_configs
from agentic_student_life.llm import LLMClient
from agentic_student_life.orchestrator import run_suite


class ControlTests(unittest.TestCase):
    def test_transient_retries_keep_the_requested_model(self):
        create = Mock(side_effect=[RuntimeError("503"), NS()])
        client = NS(chat=NS(completions=NS(create=create)))
        with (patch.object(LLMClient, "client", new_callable=PropertyMock, return_value=client),
              patch("agentic_student_life.llm.time.sleep")):
            _, used, _ = object.__new__(LLMClient)._call_with_retry("gemini:test", [])
        self.assertEqual(used, "gemini:test")
        self.assertEqual([c.kwargs["model"] for c in create.call_args_list], ["gemini:test"] * 2)

    def test_daily_quota_is_reported_without_switching_models(self):
        create = Mock(side_effect=RuntimeError("PerDay quota"))
        client = NS(chat=NS(completions=NS(create=create)))
        with patch.object(LLMClient, "client", new_callable=PropertyMock, return_value=client):
            with self.assertRaisesRegex(RuntimeError, "PerDay"):
                object.__new__(LLMClient)._call_with_retry("gemini:test", [])
        self.assertEqual(create.call_count, 1)

    def test_all_ablation_configs_use_the_same_cases(self):
        configs = load_ablation_configs()
        self.assertTrue(all(cfg.case_ids is None for cfg in configs.values()))
        self.assertEqual(len({cfg.model for key, cfg in configs.items() if key != "modelB"}), 1)
        self.assertNotEqual(configs["full"].model, configs["modelB"].model)

    def test_legacy_resume_is_rejected_before_overwriting_snapshot(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = Path(tmp) / "full"
            run.mkdir()
            (run / "outputs.jsonl").write_text("{}\n")
            (run / "config.snapshot.toml").write_text("original")
            with self.assertRaisesRegex(ValueError, "legacy protocol"):
                run_suite(cfg=RunConfig(), cases=[], profiles={}, out_root=tmp)
            self.assertEqual((run / "config.snapshot.toml").read_text(), "original")


if __name__ == "__main__":
    unittest.main()
