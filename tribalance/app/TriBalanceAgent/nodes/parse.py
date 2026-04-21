"""Node: stream-parse the Apple Health export XML into slim per-day CSVs.

Runtime process only — the raw XML never leaves the Runtime container.
Only the slim CSVs (< 1 MB typically) are forwarded to Code Interpreter.

Sleep aggregation:
  - Each sleep session's date = local date of `endDate` (wake-up).
  - `in_bed_min`  = sum of durations of all `HKCategoryValueSleepAnalysisInBed`
  - `asleep_min`  = sum of durations of all `HKCategoryValueSleepAnalysisAsleep*`

Activity aggregation (daily sum on local `startDate` date):
  - steps         = sum of HKQuantityTypeIdentifierStepCount
  - active_kcal   = sum of HKQuantityTypeIdentifierActiveEnergyBurned
  - exercise_min  = sum of HKQuantityTypeIdentifierAppleExerciseTime
"""

from __future__ import annotations

import csv
import io
from collections import defaultdict
from datetime import datetime

from lxml import etree

from state import TriBalanceState

_SLEEP_TYPE = "HKCategoryTypeIdentifierSleepAnalysis"
_SLEEP_INBED = "HKCategoryValueSleepAnalysisInBed"
_SLEEP_ASLEEP_PREFIX = "HKCategoryValueSleepAnalysisAsleep"

_QUANTITY_MAP = {
    "HKQuantityTypeIdentifierStepCount":         "steps",
    "HKQuantityTypeIdentifierActiveEnergyBurned": "active_kcal",
    "HKQuantityTypeIdentifierAppleExerciseTime":  "exercise_min",
}


def _parse_dt(s: str) -> datetime:
    # Apple Health format: "YYYY-MM-DD HH:MM:SS +HHMM" or "+HH:MM"
    try:
        return datetime.strptime(s, "%Y-%m-%d %H:%M:%S %z")
    except ValueError:
        # Try with colon in tz
        if len(s) >= 6 and (s[-3] == ":"):
            s2 = s[:-3] + s[-2:]
            return datetime.strptime(s2, "%Y-%m-%d %H:%M:%S %z")
        raise


def parse_node(state: TriBalanceState) -> dict:
    path = state["local_xml_path"]

    sleep_by_date: dict[str, dict[str, int]] = defaultdict(
        lambda: {"in_bed_min": 0, "asleep_min": 0}
    )
    activity_by_date: dict[str, dict[str, int]] = defaultdict(
        lambda: {"steps": 0, "active_kcal": 0, "exercise_min": 0}
    )
    sleep_records = 0
    activity_records = 0

    for _event, el in etree.iterparse(path, events=("end",), tag="Record"):
        type_ = el.get("type")
        if type_ == _SLEEP_TYPE:
            sleep_records += 1
            start = _parse_dt(el.get("startDate"))
            end = _parse_dt(el.get("endDate"))
            date_key = end.date().isoformat()
            minutes = int((end - start).total_seconds() // 60)
            value = el.get("value", "")
            if value == _SLEEP_INBED:
                sleep_by_date[date_key]["in_bed_min"] += minutes
            elif value.startswith(_SLEEP_ASLEEP_PREFIX):
                sleep_by_date[date_key]["asleep_min"] += minutes
        elif type_ in _QUANTITY_MAP:
            activity_records += 1
            col = _QUANTITY_MAP[type_]
            start = _parse_dt(el.get("startDate"))
            date_key = start.date().isoformat()
            try:
                value = float(el.get("value", "0"))
            except ValueError:
                value = 0.0
            activity_by_date[date_key][col] += int(value)
        # free element memory; purge previous siblings
        el.clear()
        while el.getprevious() is not None:
            del el.getparent()[0]

    dates = sorted(set(list(sleep_by_date.keys()) + list(activity_by_date.keys())))

    sleep_out = io.StringIO()
    sleep_w = csv.DictWriter(sleep_out, fieldnames=["date", "in_bed_min", "asleep_min"])
    sleep_w.writeheader()
    for d in dates:
        if d in sleep_by_date:
            sleep_w.writerow({"date": d, **sleep_by_date[d]})

    act_out = io.StringIO()
    act_w = csv.DictWriter(act_out, fieldnames=["date", "steps", "active_kcal", "exercise_min"])
    act_w.writeheader()
    for d in dates:
        if d in activity_by_date:
            act_w.writerow({"date": d, **activity_by_date[d]})

    return {
        "sleep_csv": sleep_out.getvalue(),
        "activity_csv": act_out.getvalue(),
        "parse_summary": {
            "sleep_records": sleep_records,
            "activity_records": activity_records,
            "period_days": len(dates),
        },
    }
