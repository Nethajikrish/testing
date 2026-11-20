"""Generative model of K-12 students' day-to-day behaviour.

The model produces synthetic but structured daily timelines for students in
kindergarten (grade 0) through grade 12. Each simulated student is sampled
from a grade-band profile, given latent personality traits, and then a full
24-hour day is generated as a sequence of activities:

    sleep -> morning routine -> commute -> school (class / recess / lunch)
    -> commute -> after school -> evening -> bedtime routine -> sleep

Within each free-time phase, activities are drawn from a sticky categorical
process (a "stickiness" probability keeps the previous activity going), and
durations are drawn from log-normal distributions. Traits (energy,
sociability, diligence) reweight activities so that students differ from one
another in a consistent way.

The default profiles are illustrative priors, not empirical findings. Use
`BehaviourGenerator.fit` on observed (or real, consented, de-identified) day
records to replace them with data-derived parameters.
"""

from __future__ import annotations

import copy
import datetime as dt
import math
import random
from dataclasses import dataclass
from typing import Iterable, Mapping

MINUTES_PER_DAY = 24 * 60
MIN_GRADE, MAX_GRADE = 0, 12  # 0 = kindergarten
ACTIVITIES = (
    "sleep",
    "morning_routine",
    "commute",
    "class",
    "recess",
    "lunch",
    "homework",
    "extracurricular",
    "free_play",
    "screen_time",
    "family_meal",
    "chores",
    "bedtime_routine",
)

AFTER_SCHOOL_CUT = 18 * 60  # 18:00: after-school phase ends, evening begins
MORNING_WEIGHTS = {"morning_routine": 1.0, "screen_time": 0.3, "free_play": 0.2}
BEDTIME_ROUTINE_MIN = 30
WEEKEND_MORNING_MIN = 30


@dataclass
class BandProfile:
    """Behavioural parameters for one grade band."""

    name: str
    grades: tuple[int, ...]
    wake: tuple[int, int]  # earliest, latest wake time (minutes after midnight)
    bedtime: tuple[int, int]
    school_start: int
    school_end: int
    lunch_minutes: int
    absence_rate: float  # probability a weekday is a non-school day
    stickiness: float  # probability of repeating the previous activity
    mean_minutes: dict[str, float]
    phase_weights: dict[str, dict[str, float]]


@dataclass(frozen=True)
class Traits:
    """Latent student traits, each in [0, 1]."""

    energy: float
    sociability: float
    diligence: float


@dataclass(frozen=True)
class Student:
    student_id: str
    grade: int
    band: str
    traits: Traits


@dataclass
class Event:
    start: int  # minutes after midnight
    end: int
    activity: str

    @property
    def minutes(self) -> int:
        return self.end - self.start


def _fmt(minute: int) -> str:
    return f"{minute // 60:02d}:{minute % 60:02d}"


def _parse(value: str | int) -> int:
    if isinstance(value, int):
        return value
    hours, minutes = value.split(":")
    return int(hours) * 60 + int(minutes)


def band_for_grade(grade: int) -> str:
    if not MIN_GRADE <= grade <= MAX_GRADE:
        raise ValueError(f"grade must be between {MIN_GRADE} (K) and {MAX_GRADE}, got {grade}")
    for name, profile_grades in _BAND_GRADES.items():
        if grade in profile_grades:
            return name
    raise AssertionError("unreachable")


_BAND_GRADES = {
    "K-2": (0, 1, 2),
    "3-5": (3, 4, 5),
    "6-8": (6, 7, 8),
    "9-12": (9, 10, 11, 12),
}


def default_profiles() -> dict[str, BandProfile]:
    return {
        "K-2": BandProfile(
            name="K-2",
            grades=_BAND_GRADES["K-2"],
            wake=(400, 440),
            bedtime=(1140, 1200),
            school_start=525,
            school_end=885,
            lunch_minutes=30,
            absence_rate=0.03,
            stickiness=0.35,
            mean_minutes={
                "morning_routine": 30, "class": 35, "recess": 25, "free_play": 40,
                "screen_time": 30, "homework": 20, "extracurricular": 45,
                "family_meal": 35, "chores": 20,
            },
            phase_weights={
                "school": {"class": 3.0, "recess": 2.0},
                "after_school": {"free_play": 3.0, "screen_time": 2.0, "chores": 1.0,
                                 "extracurricular": 0.5, "homework": 0.2},
                "evening": {"family_meal": 2.0, "screen_time": 1.5, "free_play": 1.0,
                            "chores": 0.7, "homework": 0.3},
                "weekend": {"free_play": 3.0, "screen_time": 2.0, "family_meal": 2.0,
                            "chores": 1.0, "extracurricular": 0.5},
            },
        ),
        "3-5": BandProfile(
            name="3-5",
            grades=_BAND_GRADES["3-5"],
            wake=(390, 430),
            bedtime=(1230, 1290),
            school_start=495,
            school_end=915,
            lunch_minutes=30,
            absence_rate=0.04,
            stickiness=0.30,
            mean_minutes={
                "morning_routine": 30, "class": 45, "recess": 20, "free_play": 35,
                "screen_time": 45, "homework": 30, "extracurricular": 60,
                "family_meal": 35, "chores": 20,
            },
            phase_weights={
                "school": {"class": 3.0, "recess": 1.5},
                "after_school": {"free_play": 2.5, "screen_time": 2.0, "homework": 1.0,
                                 "extracurricular": 1.0, "chores": 1.0},
                "evening": {"family_meal": 2.0, "homework": 1.2, "screen_time": 1.5,
                            "free_play": 1.0, "chores": 0.8},
                "weekend": {"free_play": 2.5, "screen_time": 2.5, "extracurricular": 1.0,
                            "chores": 1.0, "family_meal": 2.0},
            },
        ),
        "6-8": BandProfile(
            name="6-8",
            grades=_BAND_GRADES["6-8"],
            wake=(380, 420),
            bedtime=(1290, 1350),
            school_start=460,
            school_end=880,
            lunch_minutes=35,
            absence_rate=0.04,
            stickiness=0.25,
            mean_minutes={
                "morning_routine": 25, "class": 50, "recess": 10, "free_play": 40,
                "screen_time": 60, "homework": 45, "extracurricular": 75,
                "family_meal": 30, "chores": 20,
            },
            phase_weights={
                "school": {"class": 3.0, "recess": 0.5},
                "after_school": {"screen_time": 3.0, "homework": 2.0, "extracurricular": 1.5,
                                 "free_play": 1.0, "chores": 0.7},
                "evening": {"homework": 2.0, "screen_time": 2.5, "family_meal": 1.5,
                            "free_play": 0.8, "chores": 0.7},
                "weekend": {"screen_time": 3.0, "free_play": 1.5, "extracurricular": 1.0,
                            "family_meal": 1.5, "chores": 0.8, "homework": 0.5},
            },
        ),
        "9-12": BandProfile(
            name="9-12",
            grades=_BAND_GRADES["9-12"],
            wake=(380, 420),
            bedtime=(1320, 1380),
            school_start=450,
            school_end=900,
            lunch_minutes=35,
            absence_rate=0.05,
            stickiness=0.25,
            mean_minutes={
                "morning_routine": 25, "class": 55, "recess": 10, "free_play": 45,
                "screen_time": 70, "homework": 60, "extracurricular": 90,
                "family_meal": 30, "chores": 20,
            },
            phase_weights={
                "school": {"class": 3.0, "recess": 0.3},
                "after_school": {"homework": 2.5, "extracurricular": 2.0, "screen_time": 2.5,
                                 "free_play": 1.0, "chores": 0.5},
                "evening": {"homework": 2.5, "screen_time": 2.5, "family_meal": 1.0,
                            "free_play": 0.8, "chores": 0.5},
                "weekend": {"screen_time": 2.5, "extracurricular": 1.5, "free_play": 1.5,
                            "homework": 1.5, "family_meal": 1.0, "chores": 0.7},
            },
        ),
    }


class BehaviourGenerator:
    """Samples students and their daily timelines.

    Parameters
    ----------
    seed:
        Seed for the internal random generator, for reproducible output.
    profiles:
        Grade-band profiles; defaults to `default_profiles()`.
    """

    def __init__(self, seed: int | None = None, profiles: Mapping[str, BandProfile] | None = None):
        self.rng = random.Random(seed)
        self.profiles: dict[str, BandProfile] = copy.deepcopy(
            dict(profiles) if profiles is not None else default_profiles()
        )
        self._counter = 0

    # ----- sampling students -------------------------------------------------

    def sample_student(self, grade: int) -> Student:
        band = band_for_grade(grade)
        self._counter += 1
        traits = Traits(
            energy=self.rng.betavariate(2, 2),
            sociability=self.rng.betavariate(2, 2),
            diligence=self.rng.betavariate(2, 2),
        )
        return Student(f"S{grade:02d}-{self._counter:05d}", grade, band, traits)

    # ----- sampling days -----------------------------------------------------

    def generate_day(self, student: Student, day: dt.date) -> dict:
        profile = self.profiles[student.band]
        is_school_day = day.weekday() < 5 and self.rng.random() >= profile.absence_rate
        wake = self.rng.randint(*profile.wake)
        bedtime = self.rng.randint(*profile.bedtime)

        events: list[Event] = [Event(0, wake, "sleep")]
        if is_school_day:
            self._school_day(profile, student.traits, wake, bedtime, events)
        else:
            self._free_day(profile, student.traits, wake, bedtime, events)
        events.append(Event(bedtime - BEDTIME_ROUTINE_MIN, bedtime, "bedtime_routine"))
        events.append(Event(bedtime, MINUTES_PER_DAY, "sleep"))

        events = _merge(sorted(events, key=lambda e: e.start))
        _check_coverage(events)
        return self._to_record(student, day, is_school_day, events)

    def _school_day(self, p: BandProfile, traits: Traits, wake: int, bedtime: int,
                    events: list[Event]) -> None:
        school_start = p.school_start + self.rng.randint(-5, 5)
        school_end = p.school_end + self.rng.randint(-5, 5)
        commute_am = school_start - 20

        self._fill(p, traits, wake, commute_am, MORNING_WEIGHTS, events)
        events.append(Event(commute_am, school_start, "commute"))

        midpoint = (school_start + school_end) // 2
        lunch_start = midpoint + self.rng.randint(-20, 20)
        lunch_len = max(15, round(self.rng.gauss(p.lunch_minutes, 5)))
        lunch_end = lunch_start + lunch_len
        self._fill(p, traits, school_start, lunch_start, p.phase_weights["school"], events,
                   avoid_repeat=True)
        events.append(Event(lunch_start, lunch_end, "lunch"))
        self._fill(p, traits, lunch_end, school_end, p.phase_weights["school"], events,
                   avoid_repeat=True)

        events.append(Event(school_end, school_end + 20, "commute"))
        self._fill(p, traits, school_end + 20, AFTER_SCHOOL_CUT,
                   p.phase_weights["after_school"], events)
        self._fill(p, traits, AFTER_SCHOOL_CUT, bedtime - BEDTIME_ROUTINE_MIN,
                   p.phase_weights["evening"], events)

    def _free_day(self, p: BandProfile, traits: Traits, wake: int, bedtime: int,
                  events: list[Event]) -> None:
        morning_end = wake + WEEKEND_MORNING_MIN
        events.append(Event(wake, morning_end, "morning_routine"))
        self._fill(p, traits, morning_end, bedtime - BEDTIME_ROUTINE_MIN,
                   p.phase_weights["weekend"], events)

    def _fill(self, p: BandProfile, traits: Traits, start: int, end: int,
              weights: Mapping[str, float], events: list[Event],
              avoid_repeat: bool = False) -> None:
        """Fill [start, end) with a sticky categorical activity sequence.

        With `avoid_repeat`, the previous activity is strongly down-weighted (school
        blocks, so classes and breaks tend to alternate).
        """
        adjusted = _trait_adjusted(weights, traits)
        t, prev = start, None
        while t < end:
            names = list(adjusted)
            if avoid_repeat and prev in adjusted and len(names) > 1:
                # Soft rule: the previous activity is down-weighted, not banned.
                probs = [adjusted[n] * (0.25 if n == prev else 1.0) for n in names]
                activity = self.rng.choices(names, weights=probs)[0]
            elif prev in adjusted and self.rng.random() < p.stickiness:
                activity = prev
            else:
                activity = self.rng.choices(names, weights=[adjusted[n] for n in names])[0]
            mean = p.mean_minutes.get(activity, 30.0)
            if activity == "class":
                mean *= 0.85 + 0.3 * traits.diligence
            duration = min(self._duration(mean), end - t)
            if duration <= 0:
                break
            events.append(Event(t, t + duration, activity))
            t += duration
            prev = activity

    def _duration(self, mean: float, sigma: float = 0.3) -> int:
        mu = math.log(mean) - sigma**2 / 2
        return max(5, round(self.rng.lognormvariate(mu, sigma)))

    @staticmethod
    def _to_record(student: Student, day: dt.date, is_school_day: bool,
                   events: list[Event]) -> dict:
        totals: dict[str, int] = {}
        for e in events:
            totals[e.activity] = totals.get(e.activity, 0) + e.minutes
        return {
            "student_id": student.student_id,
            "grade": student.grade,
            "band": student.band,
            "date": day.isoformat(),
            "school_day": is_school_day,
            "traits": {
                "energy": round(student.traits.energy, 3),
                "sociability": round(student.traits.sociability, 3),
                "diligence": round(student.traits.diligence, 3),
            },
            "events": [
                {"start": _fmt(e.start), "end": _fmt(e.end), "activity": e.activity,
                 "minutes": e.minutes}
                for e in events
            ],
            "minutes_by_activity": totals,
        }

    # ----- batch generation --------------------------------------------------

    def generate(self, grades: Iterable[int], students_per_grade: int, days: int,
                 start: dt.date) -> list[dict]:
        records = []
        for grade in grades:
            for _ in range(students_per_grade):
                student = self.sample_student(grade)
                for offset in range(days):
                    records.append(self.generate_day(student, start + dt.timedelta(days=offset)))
        return records

    # ----- learning from data ------------------------------------------------

    def fit(self, records: Iterable[Mapping], min_samples: int = 5) -> dict[str, dict]:
        """Re-estimate band profiles from day records (same shape as `generate` output).

        For each band this updates the per-phase activity weights (from how often
        each activity starts in each phase) and the mean duration of each activity.
        Activities with fewer than `min_samples` observations keep their prior.
        """
        counts: dict[str, dict[str, dict[str, int]]] = {}
        durations: dict[str, dict[str, list[int]]] = {}
        for record in records:
            band = band_for_grade(int(record["grade"]))
            profile = self.profiles[band]
            for ev in record["events"]:
                activity = ev["activity"]
                start = _parse(ev["start"])
                minutes = int(ev["minutes"])
                durations.setdefault(band, {}).setdefault(activity, []).append(minutes)
                phase = _phase_of(start, bool(record["school_day"]), profile)
                if phase is not None and activity in _phase_activities(profile, phase):
                    phase_counts = counts.setdefault(band, {}).setdefault(phase, {})
                    phase_counts[activity] = phase_counts.get(activity, 0) + 1

        report: dict[str, dict] = {}
        for band, per_phase in counts.items():
            profile = self.profiles[band]
            updated_weights = {}
            for phase, weights in profile.phase_weights.items():
                observed = per_phase.get(phase, {})
                if not observed:
                    updated_weights[phase] = weights
                    continue
                updated_weights[phase] = {a: observed.get(a, 0) + 1.0 for a in weights}
            profile.phase_weights.update(updated_weights)
            report.setdefault(band, {})["phase_weights"] = updated_weights

        for band, per_activity in durations.items():
            profile = self.profiles[band]
            for activity, values in per_activity.items():
                if activity in profile.mean_minutes and len(values) >= min_samples:
                    profile.mean_minutes[activity] = sum(values) / len(values)
            report.setdefault(band, {})["mean_minutes"] = dict(profile.mean_minutes)
        return report


# ----- helpers ---------------------------------------------------------------

def _trait_adjusted(weights: Mapping[str, float], traits: Traits) -> dict[str, float]:
    out = {}
    for activity, weight in weights.items():
        factor = 1.0
        if activity == "screen_time":
            factor = 0.5 + traits.energy
        elif activity in ("free_play", "extracurricular"):
            factor = 0.5 + traits.sociability
        elif activity == "homework":
            factor = 0.5 + traits.diligence
        out[activity] = weight * factor
    return out


def _merge(events: list[Event]) -> list[Event]:
    merged: list[Event] = []
    for ev in events:
        if merged and merged[-1].activity == ev.activity and merged[-1].end == ev.start:
            merged[-1].end = ev.end
        else:
            merged.append(Event(ev.start, ev.end, ev.activity))
    return merged


def _check_coverage(events: list[Event]) -> None:
    cursor = 0
    for ev in events:
        if ev.start != cursor or ev.end <= ev.start:
            raise RuntimeError(f"timeline gap or overlap at {_fmt(cursor)}")
        cursor = ev.end
    if cursor != MINUTES_PER_DAY:
        raise RuntimeError("timeline does not cover the full day")


def _phase_of(start: int, school_day: bool, p: BandProfile) -> str | None:
    if not school_day:
        return "weekend" if start >= p.wake[0] else None
    if start < p.school_start - 20:
        return None  # morning routine: fixed weights, not fitted
    if start < p.school_end:
        return "school"
    if start < AFTER_SCHOOL_CUT:
        return "after_school"
    return "evening"


def _phase_activities(p: BandProfile, phase: str) -> tuple[str, ...]:
    return tuple(p.phase_weights[phase]) if phase in p.phase_weights else ()
