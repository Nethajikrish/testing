"""Command-line interface.

Examples:
    python -m k12_behavior --grades 0-12 --students 2 --days 3 --format json
    python -m k12_behavior --grades 4 --students 50 --days 5 --format csv --out day4.csv
    python -m k12_behavior --grades 9 --fit observed_days.json --students 10 --days 7
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import sys

from .model import BehaviourGenerator


def _parse_grades(text: str) -> list[int]:
    grades: list[int] = []
    for part in text.split(","):
        if "-" in part:
            low, high = (int(x) for x in part.split("-", 1))
            grades.extend(range(low, high + 1))
        else:
            grades.append(int(part))
    return sorted(set(grades))


def _to_csv(records: list[dict], handle) -> None:
    writer = csv.writer(handle)
    writer.writerow(["student_id", "grade", "band", "date", "school_day", "start", "end",
                     "activity", "minutes"])
    for rec in records:
        for ev in rec["events"]:
            writer.writerow([rec["student_id"], rec["grade"], rec["band"], rec["date"],
                             rec["school_day"], ev["start"], ev["end"], ev["activity"],
                             ev["minutes"]])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="k12_behavior", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--grades", default="0-12",
                        help="grades (0 = K), e.g. '0-12', '3-5' or '2,7,9' (default: 0-12)")
    parser.add_argument("--students", type=int, default=1, help="students per grade")
    parser.add_argument("--days", type=int, default=1, help="days per student")
    parser.add_argument("--start", type=dt.date.fromisoformat, default=dt.date(2026, 9, 7),
                        help="first date, YYYY-MM-DD (default: 2026-09-07)")
    parser.add_argument("--seed", type=int, default=None, help="random seed")
    parser.add_argument("--fit", metavar="FILE",
                        help="JSON file of day records (generator output) to fit profiles to")
    parser.add_argument("--format", choices=("json", "csv"), default="json")
    parser.add_argument("--out", help="output path (default: stdout)")
    args = parser.parse_args(argv)

    generator = BehaviourGenerator(seed=args.seed)
    if args.fit:
        with open(args.fit, encoding="utf-8") as fh:
            generator.fit(json.load(fh))

    records = generator.generate(_parse_grades(args.grades), args.students, args.days, args.start)

    handle = open(args.out, "w", encoding="utf-8", newline="") if args.out else sys.stdout
    try:
        if args.format == "json":
            json.dump(records, handle, indent=2)
            handle.write("\n")
        else:
            _to_csv(records, handle)
    finally:
        if args.out:
            handle.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
