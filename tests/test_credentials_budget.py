import json
from pathlib import Path
import tempfile
from types import SimpleNamespace as NS
import threading
import unittest
from unittest.mock import Mock, PropertyMock, patch

from agentic_student_life.budget import UsageBudget
from agentic_student_life.llm import LLMClient


class CredentialBudgetTests(unittest.TestCase):
    def client(self):
        llm = object.__new__(LLMClient)
        llm._local = threading.local()
        llm._gemini_credentials = [("GEMINI_API_KEY", "secret-one"),
                                    ("GEMINI_API_KEY_FREE", "secret-two")]
        return llm

    def test_quota_rotates_credentials_without_changing_model(self):
        llm = self.client()
        def create(**kw):
            if getattr(llm._local, "credential_slot", 0) == 0:
                raise RuntimeError("PerDay quota")
            return NS()
        fake = NS(chat=NS(completions=NS(create=Mock(side_effect=create))))
        with patch.object(LLMClient, "client", new_callable=PropertyMock, return_value=fake):
            _, model, _ = llm._call_with_retry("gemini:test", [])
        self.assertEqual(model, "gemini:test")
        self.assertEqual(llm._local.credential_slot, 1)
        self.assertEqual([c.kwargs["model"] for c in fake.chat.completions.create.call_args_list],
                         ["gemini:test", "gemini:test"])

    def test_exhausted_keys_are_redacted_and_stop(self):
        llm = self.client()
        create = Mock(side_effect=RuntimeError("PerDay secret-one secret-two"))
        fake = NS(chat=NS(completions=NS(create=create)))
        with patch.object(LLMClient, "client", new_callable=PropertyMock, return_value=fake):
            with self.assertRaises(RuntimeError) as caught:
                llm._call_with_retry("gemini:test", [])
        self.assertNotIn("secret-one", str(caught.exception))
        self.assertNotIn("secret-two", str(caught.exception))
        self.assertEqual(fake.chat.completions.create.call_count, 2)

    def test_retry_delay_digits_are_not_treated_as_authentication_status(self):
        llm = self.client()
        create = Mock(side_effect=[RuntimeError("429 retry in 7.3401403 seconds"),
                                   RuntimeError("429 retry in 12.403 seconds"), NS()])
        fake = NS(chat=NS(completions=NS(create=create)))
        with (patch.object(LLMClient, "client", new_callable=PropertyMock, return_value=fake),
              patch("agentic_student_life.llm.time.sleep")):
            llm._call_with_retry("gemini:test", [])
        self.assertEqual(create.call_count, 3)

    def test_budget_includes_thinking_tokens_and_logs_no_prompt(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "usage.jsonl"
            budget = UsageBudget(p, limit_usd=20, input_per_million=.75, output_per_million=3.75)
            response = NS(usage_metadata=NS(prompt_token_count=100, candidates_token_count=20,
                                           thoughts_token_count=30, total_token_count=150))
            budget.wrap(lambda **kw: response, "GEMINI_API_KEY")(model="test", contents="PRIVATE")
            rec = json.loads(p.read_text())
            self.assertEqual(rec["billable_output_tokens"], 50)
            self.assertAlmostEqual(budget.spent, .0002625)
            self.assertNotIn("PRIVATE", p.read_text())
            self.assertAlmostEqual(budget.reserved, 0)

    def test_budget_refuses_a_request_that_cannot_be_reserved(self):
        with tempfile.TemporaryDirectory() as tmp:
            budget = UsageBudget(Path(tmp)/"usage.jsonl", limit_usd=.0001,
                                 input_per_million=.75, output_per_million=3.75)
            generate = Mock()
            with self.assertRaisesRegex(RuntimeError, "no request sent"):
                budget.wrap(generate, "primary")(model="test")
            generate.assert_not_called()


if __name__ == "__main__":
    unittest.main()
