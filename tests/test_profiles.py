from pathlib import Path
import tempfile
from types import SimpleNamespace as NS
import unittest
from unittest.mock import patch

from agentic_student_life.cases.profiles import build_profiles


class ProfileTests(unittest.TestCase):
    def test_measured_scores_in_profile_prose_follow_the_current_cache(self):
        data = NS(surveys={"u19": {"loneliness_total": 56.0}}, academic={})
        with tempfile.TemporaryDirectory() as tmp, patch(
            "agentic_student_life.cases.profiles.DataStore", return_value=data
        ):
            profiles = build_profiles(out_path=Path(tmp)/"profiles.json")
        self.assertIn("UCLA=56.0", profiles["u19"]["constraints"][0])
        self.assertNotIn("UCLA=55.0", profiles["u19"]["constraints"][0])


if __name__ == "__main__":
    unittest.main()
