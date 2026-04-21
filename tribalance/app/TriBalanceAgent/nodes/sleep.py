"""Node: sleep analysis via Code Interpreter."""

from __future__ import annotations

import os
from typing import Callable

from infra.code_interpreter import CodeInterpreterWrapper
from infra.s3 import S3Client
from nodes._codegen import run_codegen_loop
from state import TriBalanceState


def make_sleep_node(
    *,
    ci: CodeInterpreterWrapper,
    s3: S3Client,
    max_attempts: int = 3,
) -> Callable[[TriBalanceState], dict]:
    def sleep_node(state: TriBalanceState) -> dict:
        bucket = os.environ.get("ARTIFACTS_S3_BUCKET")
        if not bucket:
            raise RuntimeError("ARTIFACTS_S3_BUCKET env is not set")
        metrics = run_codegen_loop(
            node_name="sleep",
            prompt_file="code_synthesis_sleep.md",
            csv_filename="sleep.csv",
            csv_content=state["sleep_csv"],
            chart_filename="sleep_trend.png",
            ci=ci,
            s3=s3,
            run_id=state["run_id"],
            artifacts_bucket=bucket,
            max_attempts=max_attempts,
        )
        return {"sleep_metrics": metrics}

    return sleep_node
