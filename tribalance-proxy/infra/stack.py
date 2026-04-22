"""TriBalance proxy CDK stack.

One Lambda function (Python 3.12), exposed via Function URL with response
streaming enabled (needed for SSE). IAM role grants:
  - bedrock-agentcore:InvokeAgentRuntime  (to forward user invocations)
  - s3:GetObject / s3:PutObject           (to mint presigned URLs)
  - secretsmanager:GetSecretValue         (future; not wired now)

Subsequent tasks (P-02, P-03, P-04) will fill in handler logic and CORS.
"""

from __future__ import annotations

from pathlib import Path

from aws_cdk import (
    CfnOutput,
    Duration,
    Stack,
    aws_iam as iam,
    aws_lambda as lambda_,
)
from constructs import Construct

AGENTCORE_AGENT_ARN = (
    "arn:aws:bedrock-agentcore:ap-northeast-2:612529367436:"
    "runtime/TriBalanceAgent-jXn0PKFg4F"
)
INPUT_BUCKET = "tribalance-input"
ARTIFACTS_BUCKET = "tribalance-artifacts"


class TriBalanceProxyStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        handler_dir = str(Path(__file__).parent.parent / "handler")

        proxy_fn = lambda_.Function(
            self,
            "ProxyFunction",
            runtime=lambda_.Runtime.PYTHON_3_12,
            handler="main.lambda_handler",
            code=lambda_.Code.from_asset(handler_dir),
            timeout=Duration.minutes(5),
            memory_size=512,
            environment={
                "AGENTCORE_AGENT_ARN": AGENTCORE_AGENT_ARN,
                "BEDROCK_REGION": "ap-northeast-2",
                "INPUT_BUCKET": INPUT_BUCKET,
                "ARTIFACTS_BUCKET": ARTIFACTS_BUCKET,
                "ALLOWED_ORIGINS": "http://localhost:5173,http://127.0.0.1:5173",
            },
        )

        # IAM: AgentCore invoke
        proxy_fn.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    "bedrock-agentcore:InvokeAgentRuntime",
                ],
                resources=[AGENTCORE_AGENT_ARN, f"{AGENTCORE_AGENT_ARN}/*"],
            )
        )

        # IAM: S3 presign (head + get on input, put/get on artifacts)
        proxy_fn.add_to_role_policy(
            iam.PolicyStatement(
                actions=["s3:PutObject", "s3:GetObject", "s3:HeadObject"],
                resources=[
                    f"arn:aws:s3:::{INPUT_BUCKET}/*",
                    f"arn:aws:s3:::{ARTIFACTS_BUCKET}/*",
                ],
            )
        )

        # TODO(Phase 3 hardening): Replace AuthType.NONE with AWS_IAM or a JWT
        # authorizer. AuthType.NONE = fully public, no auth — acceptable for the
        # Phase 1.5 local demo but MUST change before any production exposure.
        fn_url = proxy_fn.add_function_url(
            auth_type=lambda_.FunctionUrlAuthType.NONE,
            invoke_mode=lambda_.InvokeMode.RESPONSE_STREAM,
            cors=lambda_.FunctionUrlCorsOptions(
                allowed_origins=[
                    "http://localhost:5173",
                    "http://127.0.0.1:5173",
                ],
                # OPTIONS is auto-handled by Function URL service — not a
                # valid enum value here (CloudFormation validation rejects it).
                allowed_methods=[
                    lambda_.HttpMethod.GET,
                    lambda_.HttpMethod.POST,
                ],
                allowed_headers=["Content-Type", "Authorization"],
                max_age=Duration.minutes(10),
            ),
        )

        CfnOutput(self, "ProxyFunctionUrl", value=fn_url.url)
        CfnOutput(self, "ProxyFunctionArn", value=proxy_fn.function_arn)
