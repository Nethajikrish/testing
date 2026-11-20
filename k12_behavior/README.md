# K-12 Student Daily Behaviour Generative Model

A generative model that produces realistic, structured 24-hour timelines of
students' day-to-day behaviour for grades K (0) through 12. It has no
dependencies beyond the Python standard library and needs no API key.

It is a probabilistic generative model (not a large language model): each
student is sampled from a grade band, given personality traits, and each day is
sampled as a sequence of activities (sleep, routine, commute, class, recess,
lunch, homework, extracurricular, free play, screen time, family meal, chores,
bedtime routine) that respects a school schedule on school days.

## How it works

1. **Grade band** – K-2, 3-5, 6-8 or 9-12 selects a profile (wake/bedtime
   windows, school hours, lunch length, absence rate, typical durations, and
   activity weights for school, after-school, evening and weekend phases).
2. **Student traits** – `energy`, `sociability` and `diligence` are sampled from
   Beta(2, 2) and reweight activities (e.g. high energy → more screen time).
3. **Day generation** – fixed anchors (commutes, lunch, bedtime routine, sleep)
   are placed with jitter; the free time between them is filled by a sticky
   categorical process with log-normal durations. Every day is checked to cover
   exactly 24 hours with no gaps or overlaps.
4. **Fitting** – `BehaviourGenerator.fit(records)` re-estimates the activity
   weights and mean durations for each band from real records, so the priors can
   be replaced with data-derived parameters.

The built-in profiles are **illustrative priors, not empirical findings**. Do
not treat their output as evidence about real children.

## Usage

```bash
# JSON for grades K-12, two students per grade, three days each
python3 -m k12_behavior --grades 0-12 --students 2 --days 3 --seed 42

# CSV (one row per activity) for grade 4
python3 -m k12_behavior --grades 4 --students 50 --days 5 --format csv --out grade4.csv

# Re-fit the profiles to earlier output, then generate
python3 -m k12_behavior --grades 9 --fit observed_days.json --students 10 --days 7
```

Python API:

```python
import datetime as dt
from k12_behavior import BehaviourGenerator

gen = BehaviourGenerator(seed=1)
records = gen.generate(grades=[0, 5, 9], students_per_grade=2, days=5,
                       start=dt.date(2026, 9, 7))
gen.fit(records)  # learn from records (same shape as the output)
```

Each record contains `student_id`, `grade`, `band`, `date`, `school_day`,
`traits`, `events` (start/end as `HH:MM`, activity, minutes) and
`minutes_by_activity`.

## Tests

```bash
python3 -m unittest discover -s k12_behavior/tests -t .
```

## Privacy and use

Output is synthetic and contains no real student data. Do not use it to
profile, monitor or make decisions about real children. If you fit the model
to real data, use de-identified, consented data and follow your local
student-data regulations (for example FERPA or GDPR).
