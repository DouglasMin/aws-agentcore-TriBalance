"""Smoke test: CDK stack synth must succeed."""

from __future__ import annotations

from unittest.mock import patch

from aws_cdk import App, Environment, assertions

from infra.stack import TriBalanceProxyStack


def test_stack_synthesizes():
    # Mock pip install so the deps layer doesn't actually download packages
    with patch("infra.stack.subprocess.check_call"):
        app = App()
        stack = TriBalanceProxyStack(
            app,
            "TestProxy",
            env=Environment(account="612529367436", region="ap-northeast-2"),
        )
        template = assertions.Template.from_stack(stack)

    # 1 Lambda function
    template.resource_count_is("AWS::Lambda::Function", 1)

    # Function URL resource exists
    template.resource_count_is("AWS::Lambda::Url", 1)

    # 2 Lambda layers: LWA (imported) + deps (created)
    template.resource_count_is("AWS::Lambda::LayerVersion", 1)  # only the deps layer is a resource; LWA is imported

    # Env vars are wired (including LWA config)
    template.has_resource_properties(
        "AWS::Lambda::Function",
        {
            "Environment": {
                "Variables": assertions.Match.object_like({
                    "AGENTCORE_AGENT_ARN": assertions.Match.string_like_regexp(
                        "arn:aws:bedrock-agentcore:.*:runtime/TriBalanceAgent-"
                    ),
                    "BEDROCK_REGION": "ap-northeast-2",
                    "INPUT_BUCKET": "tribalance-input",
                    "ARTIFACTS_BUCKET": "tribalance-artifacts",
                    "AWS_LWA_PORT": "8080",
                    "AWS_LWA_INVOKE_MODE": "response_stream",
                    "AWS_LAMBDA_EXEC_WRAPPER": "/opt/bootstrap",
                }),
            },
        },
    )

    # Handler is run.sh (LWA startup script)
    template.has_resource_properties(
        "AWS::Lambda::Function",
        {"Handler": "run.sh"},
    )

    # IAM policies present
    synth = template.to_json()
    doc_str = str(synth)
    assert "bedrock-agentcore:InvokeAgentRuntime" in doc_str
    assert "s3:PutObject" in doc_str
