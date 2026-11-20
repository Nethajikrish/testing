import datetime as dt
import json
import unittest

from k12_behavior import BehaviourGenerator, band_for_grade
from k12_behavior.model import MINUTES_PER_DAY, _parse


class BandTests(unittest.TestCase):
    def test_grade_bands(self):
        self.assertEqual(band_for_grade(0), "K-2")
        self.assertEqual(band_for_grade(2), "K-2")
        self.assertEqual(band_for_grade(5), "3-5")
        self.assertEqual(band_for_grade(8), "6-8")
        self.assertEqual(band_for_grade(12), "9-12")

    def test_invalid_grade(self):
        for grade in (-1, 13):
            with self.assertRaises(ValueError):
                band_for_grade(grade)


class DayTests(unittest.TestCase):
    def setUp(self):
        self.gen = BehaviourGenerator(seed=123)

    def test_every_day_covers_24_hours_without_gaps(self):
        for grade in range(0, 13):
            student = self.gen.sample_student(grade)
            for offset in range(10):
                rec = self.gen.generate_day(student, dt.date(2026, 9, 7) + dt.timedelta(days=offset))
                cursor = 0
                for ev in rec["events"]:
                    start, end = _parse(ev["start"]), _parse(ev["end"])
                    self.assertEqual(start, cursor)
                    self.assertGreater(end, start)
                    cursor = end
                self.assertEqual(cursor, MINUTES_PER_DAY)
                self.assertEqual(sum(rec["minutes_by_activity"].values()), MINUTES_PER_DAY)

    def test_school_days_have_school_activities_and_weekends_do_not(self):
        student = self.gen.sample_student(7)
        for _ in range(30):
            rec = self.gen.generate_day(student, dt.date(2026, 9, 9))  # Wednesday
            if rec["school_day"]:
                self.assertIn("class", rec["minutes_by_activity"])
                self.assertIn("lunch", rec["minutes_by_activity"])
            sat = self.gen.generate_day(student, dt.date(2026, 9, 12))  # Saturday
            self.assertFalse(sat["school_day"])
            self.assertNotIn("class", sat["minutes_by_activity"])
            self.assertNotIn("lunch", sat["minutes_by_activity"])

    def test_sleep_is_within_expected_range_for_kindergarten(self):
        student = self.gen.sample_student(0)
        hours = []
        for _ in range(40):
            rec = self.gen.generate_day(student, dt.date(2026, 9, 7))
            hours.append(rec["minutes_by_activity"]["sleep"] / 60)
        self.assertTrue(9 <= sum(hours) / len(hours) <= 13)

    def test_seed_is_reproducible(self):
        a = BehaviourGenerator(seed=5).generate([3, 9], 2, 2, dt.date(2026, 1, 5))
        b = BehaviourGenerator(seed=5).generate([3, 9], 2, 2, dt.date(2026, 1, 5))
        self.assertEqual(a, b)

    def test_traits_are_in_unit_interval(self):
        for _ in range(50):
            t = self.gen.sample_student(4).traits
            for value in (t.energy, t.sociability, t.diligence):
                self.assertTrue(0.0 <= value <= 1.0)


class FitTests(unittest.TestCase):
    def test_fit_updates_mean_durations_from_observed_data(self):
        source = BehaviourGenerator(seed=11)
        records = source.generate([10], students_per_grade=30, days=10, start=dt.date(2026, 1, 5))
        learner = BehaviourGenerator(seed=0)
        before = dict(learner.profiles["9-12"].mean_minutes)
        report = learner.fit(records)
        after = learner.profiles["9-12"].mean_minutes
        self.assertIn("9-12", report)
        self.assertNotEqual(before["screen_time"], after["screen_time"])
        # Fitted screen-time mean should be near the value that generated the data.
        observed = [e["minutes"] for r in records for e in r["events"] if e["activity"] == "screen_time"]
        self.assertAlmostEqual(after["screen_time"], sum(observed) / len(observed), places=6)

    def test_fitted_generator_still_produces_valid_days(self):
        records = BehaviourGenerator(seed=2).generate([5], 10, 5, dt.date(2026, 1, 5))
        gen = BehaviourGenerator(seed=3)
        gen.fit(json.loads(json.dumps(records)))
        for rec in gen.generate([5], 3, 3, dt.date(2026, 2, 2)):
            self.assertEqual(sum(rec["minutes_by_activity"].values()), MINUTES_PER_DAY)


if __name__ == "__main__":
    unittest.main()
