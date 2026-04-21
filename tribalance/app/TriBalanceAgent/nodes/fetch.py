"""Node: download the source Apple Health XML from S3 to a local temp path."""

from __future__ import annotations

import os
import uuid
from pathlib import Path
from typing import Callable

from infra.s3 import S3Client
from state import TriBalanceState


def make_fetch_node(*, s3: S3Client, tmp_root: Path) -> Callable[[TriBalanceState], dict]:
    def fetch_node(state: TriBalanceState) -> dict:
        if "s3_key" not in state:
            raise KeyError("state is missing 's3_key'")
        bucket = os.environ.get("INPUT_S3_BUCKET")
        if not bucket:
            raise RuntimeError("INPUT_S3_BUCKET env is not set")

        filename = f"{uuid.uuid4().hex}.xml"
        dest = tmp_root / filename
        s3.download(bucket, state["s3_key"], dest)
        return {"local_xml_path": str(dest)}

    return fetch_node
