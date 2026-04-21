"""Node: activity analysis via Code Interpreter."""

from __future__ import annotations

import os
from typing import Callable

from infra.code_interpreter import CodeInterpreterWrapper
from infra.s3 import S3Client
from nodes._codegen import run_codegen_loop
from state import TriBalanceState


def make_activity_node(
    *,
    ci: CodeInterpreterWrapper,
    s3: S3Client,
    max_attempts: int = 3,
) -> Callable[[TriBalanceState], dict]:
    def activity_node(state: TriBalanceState) -> dict:
        metrics = run_codegen_loop(
            node_name="activity",
            prompt_file="code_synthesis_activity.md",
            csv_filename="activity.csv",
            csv_content=state["activity_csv"],
            chart_filename="activity_trend.png",
            ci=ci,
            s3=s3,
            run_id=state["run_id"],
            artifacts_bucket=os.environ["ARTIFACTS_S3_BUCKET"],
            max_attempts=max_attempts,
        )
        return {"activity_metrics": metrics}

    return activity_node
