#!/bin/bash
# Local AgentCore dev server with hot-reload via volume mount.
# AWS profile is forwarded to the container; ~/.aws is mounted read-only.

set -euo pipefail

export AWS_PROFILE="${AWS_PROFILE:-developer-dongik}"
export BEDROCK_REGION="${BEDROCK_REGION:-us-west-2}"
export ARTIFACTS_S3_BUCKET="${ARTIFACTS_S3_BUCKET:-tribalance-artifacts}"
export INPUT_S3_BUCKET="${INPUT_S3_BUCKET:-tribalance-input}"
export LLM_PROVIDER="${LLM_PROVIDER:-openai}"
export LANGSMITH_TRACING="${LANGSMITH_TRACING:-true}"
export LANGSMITH_PROJECT="${LANGSMITH_PROJECT:-TriBalance}"

agentcore dev
