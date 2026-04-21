#!/bin/bash
# One-time S3 bucket creation for TriBalance input + artifacts.
# Requires AWS_PROFILE set and appropriate IAM.

set -euo pipefail

: "${AWS_PROFILE:?set AWS_PROFILE}"
REGION="${BEDROCK_REGION:-ap-northeast-2}"
INPUT="${INPUT_S3_BUCKET:-tribalance-input}"
ARTIFACTS="${ARTIFACTS_S3_BUCKET:-tribalance-artifacts}"

for bucket in "$INPUT" "$ARTIFACTS"; do
  if aws s3api head-bucket --bucket "$bucket" --region "$REGION" 2>/dev/null; then
    echo "  exists: $bucket"
  else
    echo "  creating: $bucket"
    aws s3api create-bucket \
      --bucket "$bucket" \
      --region "$REGION" \
      --create-bucket-configuration LocationConstraint="$REGION"
  fi
done
