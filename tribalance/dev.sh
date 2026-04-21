#!/bin/bash
# agentcore dev wrapper — sources agentcore/.env.local so the CLI forwards
# those env vars into the local dev container. Mirrors the finance-ai-app pattern.

set -euo pipefail

if [ -f ./agentcore/.env.local ]; then
    set -a
    source ./agentcore/.env.local
    set +a
fi

export AWS_PROFILE="${AWS_PROFILE:-developer-dongik}"

agentcore dev "$@"
