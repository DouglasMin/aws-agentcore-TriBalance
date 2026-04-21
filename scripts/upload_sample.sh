#!/bin/bash
# Upload the test fixture XML to INPUT_S3_BUCKET so you can invoke the agent.

set -euo pipefail

: "${AWS_PROFILE:?set AWS_PROFILE}"
INPUT="${INPUT_S3_BUCKET:-tribalance-input}"
KEY="samples/export_sample.xml"
FILE="tribalance/app/TriBalanceAgent/tests/fixtures/export_sample.xml"

aws s3 cp "$FILE" "s3://${INPUT}/${KEY}"
echo "uploaded: s3://${INPUT}/${KEY}"
