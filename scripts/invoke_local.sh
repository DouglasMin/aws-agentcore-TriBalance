#!/bin/bash
# Invoke the deployed TriBalanceAgent with the sample payload.

set -euo pipefail

: "${AWS_PROFILE:?set AWS_PROFILE}"

agentcore invoke --payload '{
  "s3_key": "samples/export_sample.xml",
  "week_start": "2026-04-06"
}'
