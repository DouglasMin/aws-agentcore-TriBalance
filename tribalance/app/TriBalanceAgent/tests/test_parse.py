import csv
from io import StringIO
from pathlib import Path

from nodes.parse import parse_node


FIXTURE = Path(__file__).parent / "fixtures" / "export_sample.xml"


def _rows(csv_str: str) -> list[dict[str, str]]:
    return list(csv.DictReader(StringIO(csv_str)))


def test_parse_returns_both_csvs_and_summary():
    state = {"local_xml_path": str(FIXTURE)}
    out = parse_node(state)

    assert "sleep_csv" in out
    assert "activity_csv" in out
    assert out["parse_summary"]["period_days"] == 5


def test_sleep_csv_has_one_row_per_night():
    state = {"local_xml_path": str(FIXTURE)}
    out = parse_node(state)
    rows = _rows(out["sleep_csv"])
    dates = [r["date"] for r in rows]
    assert dates == ["2026-04-02", "2026-04-03", "2026-04-04", "2026-04-05", "2026-04-06"]
    first = rows[0]
    # Night 1: InBed 2026-04-01 23:10 -> 2026-04-02 07:05 = 7h 55m = 475 min
    assert int(first["in_bed_min"]) == 475
    # Asleep same night: 23:20 -> 06:55 = 7h 35m = 455 min
    assert int(first["asleep_min"]) == 455


def test_activity_csv_has_one_row_per_day():
    state = {"local_xml_path": str(FIXTURE)}
    out = parse_node(state)
    rows = _rows(out["activity_csv"])
    dates = [r["date"] for r in rows]
    assert dates == ["2026-04-02", "2026-04-03", "2026-04-04", "2026-04-05", "2026-04-06"]
    day3 = rows[2]
    assert int(day3["steps"]) == 12045
    assert int(day3["active_kcal"]) == 720
    assert int(day3["exercise_min"]) == 52


def test_parse_summary_counts():
    state = {"local_xml_path": str(FIXTURE)}
    out = parse_node(state)
    s = out["parse_summary"]
    # 5 nights × 2 records = 10 sleep, 5 days × 3 quantity types = 15 activity
    assert s["sleep_records"] == 10
    assert s["activity_records"] == 15
