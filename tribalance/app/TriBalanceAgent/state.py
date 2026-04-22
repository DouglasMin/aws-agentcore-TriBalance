"""LangGraph state schema for the TriBalance pipeline.

All fields are Optional/total=False because the graph populates them
progressively across nodes.
"""

from __future__ import annotations

from typing import Literal, TypedDict

Trend = Literal["up", "down", "stable"]


class Metrics(TypedDict):
    avg: dict               # {"duration_hr": 6.8, ...}
    trend: Trend
    chart_s3_key: str


class TriBalanceState(TypedDict, total=False):
    # input
    s3_key: str
    week_start: str         # ISO date (Monday of the analysis week)
    run_id: str

    # working (populated by parse)
    local_xml_path: str
    sleep_csv: str
    activity_csv: str
    parse_summary: dict
    sleep_series: list[dict]
    activity_series: list[dict]

    # analysis
    sleep_metrics: Metrics
    activity_metrics: Metrics
    insights: list[str]

    # final
    plan: str

    # bookkeeping
    errors: list[dict]
