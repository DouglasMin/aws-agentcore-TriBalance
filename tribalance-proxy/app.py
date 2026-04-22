#!/usr/bin/env python3
"""CDK entrypoint for the TriBalance proxy Lambda."""

from aws_cdk import App, Environment

from infra.stack import TriBalanceProxyStack

app = App()

TriBalanceProxyStack(
    app,
    "TriBalanceProxy",
    env=Environment(account="612529367436", region="ap-northeast-2"),
    description="Lambda Function URL proxy: SSE streaming to AgentCore Runtime + S3 presigned URLs",
)

app.synth()
