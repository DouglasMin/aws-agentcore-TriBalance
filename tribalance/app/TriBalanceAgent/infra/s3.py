"""Minimal S3 client used by fetch + artifact-upload nodes."""

from __future__ import annotations

from pathlib import Path

import boto3


class S3Client:
    def __init__(self, region: str):
        self._client = boto3.client("s3", region_name=region)

    def download(self, bucket: str, key: str, dest: Path) -> None:
        dest.parent.mkdir(parents=True, exist_ok=True)
        response = self._client.get_object(Bucket=bucket, Key=key)
        body = response["Body"]
        with open(dest, "wb") as f:
            for chunk in iter(lambda: body.read(1 << 16), b""):
                f.write(chunk)

    def upload_bytes(self, bucket: str, key: str, data: bytes, content_type: str) -> None:
        self._client.put_object(
            Bucket=bucket,
            Key=key,
            Body=data,
            ContentType=content_type,
        )
