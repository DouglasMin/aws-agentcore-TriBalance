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
from datetime import datetime, timedelta

from lxml import etree

from events import emit
from state import TriBalanceState

_SLEEP_TYPE = "HKCategoryTypeIdentifierSleepAnalysis"
_SLEEP_INBED = "HKCategoryValueSleepAnalysisInBed"
_SLEEP_ASLEEP_PREFIX = "HKCategoryValueSleepAnalysisAsleep"

_QUANTITY_MAP = {
    "HKQuantityTypeIdentifierStepCount":         "steps",
    "HKQuantityTypeIdentifierActiveEnergyBurned": "active_kcal",
    "HKQuantityTypeIdentifierAppleExerciseTime":  "exercise_min",
}

# Activity double-count guard: iPhone and Apple Watch log overlapping step
# counts. To avoid summing both, we aggregate Watch and "other" (iPhone /
# 3rd-party) records into SEPARATE buckets, then at series-construction
# time pick per-day: Watch if any Watch data exists that day, otherwise
# fall back to other. This keeps the pipeline usable for Watch-less users
# while preventing the 2× double-count when both are present.
# Sleep records are NOT split because many users intentionally rely on
# 3rd-party sleep trackers (AutoSleep, SleepCycle, etc.).
_WATCH_HINT = "watch"

# After parsing, keep only the most recent N days of aggregated data. Prevents
# multi-year exports from overwhelming downstream Code Interpreter prompts.
_KEEP_RECENT_DAYS = 14


class EmptyExportError(ValueError):
    """Raised when the parsed XML contains no usable sleep/activity records.

    Caught in main.py's entrypoint and re-emitted as an ``error`` SSE event
    so the UI can show a clear, user-actionable message.
    """


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
    activity_watch: dict[str, dict[str, int]] = defaultdict(
        lambda: {"steps": 0, "active_kcal": 0, "exercise_min": 0}
    )
    activity_other: dict[str, dict[str, int]] = defaultdict(
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
            minutes = int((end - start).total_seconds() // 60)
            # Apple Health occasionally exports malformed records where
            # endDate <= startDate. Skip such records silently.
            if minutes <= 0:
                el.clear()
                while el.getprevious() is not None:
                    del el.getparent()[0]
                continue
            date_key = end.date().isoformat()
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
            source = (el.get("sourceName") or "").lower()
            bucket = activity_watch if _WATCH_HINT in source else activity_other
            # round (not truncate) to avoid systematic undercount on kcal,
            # and floor at zero to swallow malformed negatives.
            bucket[date_key][col] += max(0, round(value))
        # free element memory; purge previous siblings
        el.clear()
        while el.getprevious() is not None:
            del el.getparent()[0]

    # Merge activity per-metric: take max(watch, other) for each column.
    # Why max() — the Watch logs kcal/exercise that iPhone doesn't (so for
    # those metrics the Watch's value wins, iPhone's is 0). Steps are logged
    # by both; taking the max avoids double-counting while preserving the
    # higher-fidelity source (usually Watch, but iPhone wins on days the
    # Watch wasn't worn). Mirrors Apple Health app's own display logic.
    activity_by_date: dict[str, dict[str, int]] = {}
    for d in set(list(activity_watch.keys()) + list(activity_other.keys())):
        w = activity_watch.get(d) or {"steps": 0, "active_kcal": 0, "exercise_min": 0}
        o = activity_other.get(d) or {"steps": 0, "active_kcal": 0, "exercise_min": 0}
        activity_by_date[d] = {
            "steps":        max(w["steps"], o["steps"]),
            "active_kcal":  max(w["active_kcal"], o["active_kcal"]),
            "exercise_min": max(w["exercise_min"], o["exercise_min"]),
        }

    all_dates = sorted(set(list(sleep_by_date.keys()) + list(activity_by_date.keys())))

    # Empty export guard — either the file had no supported records, or
    # sourceName filtering removed everything. Raise a typed error so the
    # graph can surface a specific message to the UI.
    if not all_dates:
        raise EmptyExportError(
            "no sleep/activity records found — is this an Apple Health export.xml "
            "with Apple Watch data? (file had 0 matching records after filtering)"
        )

    # Trim to last _KEEP_RECENT_DAYS from the MAX date seen in the file.
    # Anchoring on the data (not on "today") keeps sample exports usable
    # and naturally scopes multi-year exports to the most recent window.
    max_date = datetime.strptime(all_dates[-1], "%Y-%m-%d").date()
    window_start = (max_date - timedelta(days=_KEEP_RECENT_DAYS - 1)).isoformat()
    dates = [d for d in all_dates if d >= window_start]

    sleep_out = io.StringIO()
    sleep_w = csv.DictWriter(sleep_out, fieldnames=["date", "in_bed_min", "asleep_min"])
    sleep_w.writeheader()

    act_out = io.StringIO()
    act_w = csv.DictWriter(act_out, fieldnames=["date", "steps", "active_kcal", "exercise_min"])
    act_w.writeheader()

    sleep_series = []
    activity_series = []

    for d in dates:
        s = sleep_by_date.get(d)
        if s is not None:
            sleep_w.writerow({"date": d, **s})
            in_bed_min = s["in_bed_min"]
            asleep_min = s["asleep_min"]
            sleep_series.append({
                "date": d,
                "asleep_hr": round(asleep_min / 60, 2),
                "in_bed_hr": round(in_bed_min / 60, 2),
                "efficiency": round(min(asleep_min, in_bed_min) / in_bed_min, 3) if in_bed_min > 0 else 0.0,
            })
        a = activity_by_date.get(d)
        if a is not None:
            act_w.writerow({"date": d, **a})
            activity_series.append({
                "date": d,
                "steps": a["steps"],
                "active_kcal": a["active_kcal"],
                "exercise_min": a["exercise_min"],
            })

    emit({"event": "parsed_series", "sleep": sleep_series, "activity": activity_series})

    return {
        "sleep_csv": sleep_out.getvalue(),
        "activity_csv": act_out.getvalue(),
        "sleep_series": sleep_series,
        "activity_series": activity_series,
        "parse_summary": {
            "sleep_records": sleep_records,
            "activity_records": activity_records,
            "period_days": len(dates),
        },
    }
