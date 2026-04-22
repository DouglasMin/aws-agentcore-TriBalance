"""Smoke test: CDK stack synth must succeed."""

from __future__ import annotations

from aws_cdk import App, Environment, assertions

from infra.stack import TriBalanceProxyStack


def test_stack_synthesizes():
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

    # Env vars are wired
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
                }),
            },
        },
    )

    # IAM: AgentCore invoke policy statement is attached (grep synth)
    synth = template.to_json()
    doc_str = str(synth)
    assert "bedrock-agentcore:InvokeAgentRuntime" in doc_str
    assert "s3:PutObject" in doc_str
