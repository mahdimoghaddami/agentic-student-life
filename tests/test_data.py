"""Small synthetic fixtures exercise causal boundaries without the raw dataset."""
import json
from pathlib import Path
import tempfile
import unittest

import pandas as pd

from agentic_student_life.data.features import intersect_intervals, merge_intervals
from agentic_student_life.data.loaders import TZ, load_ema
from agentic_student_life.data.store import DataStore


class DataTests(unittest.TestCase):
    def test_interval_intersection_and_bridging(self):
        self.assertEqual(intersect_intervals([(0, 10), (20, 30)], [(5, 25)]), [(5, 10), (20, 25)])
        self.assertEqual(merge_intervals([(20, 30), (0, 10)], gap=10), [(0, 30)])

    def test_sleep_closes_at_noon_and_ema_uses_exact_time(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)
            for name in ("surveys", "academic"):
                (p / f"{name}.json").write_text("{}")
            pd.DataFrame({
                "date": pd.to_datetime(["2013-04-01", "2013-04-02", "2013-04-03"]),
                "has_sleep": [True] * 3, "sleep_hours_inferred": [7., 6., 9.],
                "bedtime": ["23:00"] * 3, "wake_time": ["06:00"] * 3,
            }).to_parquet(p / "daily_u00.parquet")
            pd.DataFrame({"time": pd.to_datetime(["2013-04-02T13:00Z", "2013-04-02T18:00Z"]),
                          "type": ["stress", "stress"]}).to_parquet(p / "ema_u00.parquet")
            ds = DataStore(p)
            morning = ds.get_view("u00", "2013-04-02 10:00")
            self.assertIsNone(morning.last_night)
            self.assertEqual(len(morning.ema), 1)
            noon = ds.get_view("u00", "2013-04-02 12:00")
            self.assertEqual(noon.last_night["sleep_hours_inferred"], 6)
            self.assertTrue((noon.daily["date"] < pd.Timestamp("2013-04-02")).all())
            # Altering the future leaves all available observations unchanged.
            ds._daily["u00"].loc[2, "sleep_hours_inferred"] = 100
            pd.testing.assert_frame_equal(noon.daily, ds.get_view("u00", "2013-04-02 12:00").daily)

    def test_stress_remapping_and_empty_ema_schema(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "EMA/response/Stress"
            path.mkdir(parents=True)
            (path / "Stress_u00.json").write_text(json.dumps([
                {"level": "3", "resp_time": 1364904000}, {"level": "5", "resp_time": 1364904100}]))
            self.assertEqual(load_ema(tmp, "u00")["stress"].tolist(), [5, 1])
            self.assertEqual(str(load_ema(tmp, "u01")["time"].dt.tz), TZ)


if __name__ == "__main__":
    unittest.main()
