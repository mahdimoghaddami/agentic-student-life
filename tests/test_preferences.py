import unittest
from agentic_student_life.eval.metrics import check_preference_adherence, preference_violations


class PreferenceTests(unittest.TestCase):
    def setUp(self):
        self.first = {"case_id": "first", "participant_id": "u00",
                      "decision_time": "2013-04-10T20:00:00-04:00",
                      "scripted_feedback": {"forbidden_terms": ["run", "gym"],
                        "required_themes": ["tea", "breath"], "feedback_text": "Keep it under 10 words."}}
        self.case = {"case_id": "second", "participant_id": "u00", "step": 2,
                     "category": "preference_update", "decision_time": "2013-04-12T20:00:00-04:00",
                     "scripted_feedback": {"forbidden_terms": ["tea"]}}
        self.cases = {"first": self.first, "second": self.case}

    def check(self, msg):
        return check_preference_adherence({"final_message": msg}, self.case, self.cases)

    def test_checks_themes_length_and_forbidden_terms(self):
        self.assertTrue(self.check("Pause for tea and a few slow breaths."))
        self.assertFalse(self.check("banana " * 100))
        self.assertFalse(self.check("Try the gym, then tea."))
        self.assertFalse(self.check("tea " * 10))  # 'under 10' is strict.
        self.assertTrue(self.check("Deadlines are running high; pause for tea."))

    def test_current_and_future_feedback_do_not_change_current_score(self):
        self.assertTrue(self.check("Pause for tea."))
        future = {**self.first, "case_id": "future", "decision_time": "2013-04-20T20:00:00-04:00",
                  "scripted_feedback": {"forbidden_terms": ["tea"]}}
        self.cases["future"] = future
        self.assertTrue(self.check("Pause for tea."))

    def test_failure_and_missing_history_cannot_count_as_adherent(self):
        rec = {"status": "failed", "final_message": "Pause for tea."}
        self.assertFalse(check_preference_adherence(rec, self.case, self.cases))
        self.assertIsNone(check_preference_adherence(rec, self.case, {}))


if __name__ == "__main__":
    unittest.main()
