"""TriBalance proxy CDK stack.

Uses Lambda Web Adapter (LWA) to run a FastAPI app inside Lambda, enabling
true SSE response streaming via Function URL RESPONSE_STREAM mode.

Architecture:
  - Lambda layer: LWA v1.0.0 (public ECR layer)
  - Lambda layer: Python deps (fastapi, uvicorn, etc.) built locally
  - Handler: run.sh → uvicorn handler.app:app
  - LWA forwards Function URL requests to the FastAPI app on port 8080
  - FastAPI StreamingResponse yields SSE frames in real time

IAM role grants:
  - bedrock-agentcore:InvokeAgentRuntime  (to forward user invocations)
  - s3:GetObject / s3:PutObject           (to mint presigned URLs)
"""

from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

from aws_cdk import (
    CfnOutput,
    Duration,
    RemovalPolicy,
    Stack,
    aws_cloudwatch as cloudwatch,
    aws_iam as iam,
    aws_lambda as lambda_,
    aws_logs as logs,
    aws_secretsmanager as secretsmanager,
)
from constructs import Construct

AGENTCORE_AGENT_ARN = (
    "arn:aws:bedrock-agentcore:ap-northeast-2:612529367436:"
    "runtime/TriBalanceAgent-jXn0PKFg4F"
)
INPUT_BUCKET = "tribalance-input"
ARTIFACTS_BUCKET = "tribalance-artifacts"

# Lambda Web Adapter v1.0.0 public layer (x86_64)
# See: https://github.com/aws/aws-lambda-web-adapter
LWA_LAYER_ARN = "arn:aws:lambda:ap-northeast-2:753240598075:layer:LambdaAdapterLayerX86:27"

# Python packages that must be present in the Lambda environment for the
# FastAPI/uvicorn app to run. boto3/botocore ship with the Lambda runtime.
_PIP_DEPS = ["fastapi", "uvicorn"]


def _build_deps_layer_code() -> lambda_.Code:
    """pip-install FastAPI + uvicorn into a temp dir structured as a layer.

    Layer zip layout:  python/lib/python3.12/site-packages/...
    Lambda automatically adds this to sys.path.
    """
    tmp = tempfile.mkdtemp(prefix="tribalance-deps-")
    target = Path(tmp) / "python"
    subprocess.check_call(  # noqa: S603
        [  # noqa: S607
            "uv", "pip", "install", "--quiet",
            "--python-platform", "x86_64-manylinux2014",
            "--python-version", "3.12",
            "--target", str(target),
            *_PIP_DEPS,
        ],
    )
    return lambda_.Code.from_asset(tmp)


class TriBalanceProxyStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        project_root = str(Path(__file__).parent.parent)

        # Auth token — shared secret between proxy Lambda and frontend.
        # CDK auto-generates on first deploy and stores in Secrets Manager.
        # Lambda reads via boto3 at cold start (once, cached for the life of
        # the execution environment). Frontend operator must fetch the value
        # manually (`aws secretsmanager get-secret-value --secret-id ...`)
        # and paste into .env.local as VITE_PROXY_TOKEN.
        app_token_secret = secretsmanager.Secret(
            self,
            "AppToken",
            description="TriBalance proxy API auth token (Bearer <value>)",
            generate_secret_string=secretsmanager.SecretStringGenerator(
                password_length=48,
                exclude_characters="\"/\\'@`:",
                exclude_punctuation=False,
            ),
        )

        # LWA layer — enables streaming from a FastAPI/uvicorn app
        lwa_layer = lambda_.LayerVersion.from_layer_version_arn(
            self, "LWALayer", LWA_LAYER_ARN
        )

        # Python deps layer — fastapi + uvicorn (not in Lambda runtime)
        deps_layer = lambda_.LayerVersion(
            self,
            "DepsLayer",
            code=_build_deps_layer_code(),
            compatible_runtimes=[lambda_.Runtime.PYTHON_3_12],
            description="FastAPI + uvicorn for TriBalance proxy",
        )

        # Own the Lambda's CloudWatch log group so we control retention.
        # (Lambda auto-creates if unspecified, with retention=never-expire.)
        proxy_log_group = logs.LogGroup(
            self,
            "ProxyLogGroup",
            retention=logs.RetentionDays.ONE_MONTH,
            removal_policy=RemovalPolicy.DESTROY,
        )

        proxy_fn = lambda_.Function(
            self,
            "ProxyFunction",
            runtime=lambda_.Runtime.PYTHON_3_12,
            log_group=proxy_log_group,
            # LWA intercepts the handler; run.sh starts uvicorn
            handler="run.sh",
            code=lambda_.Code.from_asset(
                project_root,
                exclude=[
                    ".venv",
                    ".venv/**",
                    "**/__pycache__",
                    "**/*.pyc",
                    "tests",
                    "tests/**",
                    "infra",
                    "infra/**",
                    "cdk.out",
                    "cdk.out/**",
                    "cdk.json",
                    "pyproject.toml",
                    "uv.lock",
                    ".python-version",
                    "README.md",
                    ".ruff_cache/**",
                    ".pytest_cache/**",
                ],
            ),
            layers=[lwa_layer, deps_layer],
            # 10-min timeout: real Apple Health exports (100-400MB) can take
            # 1-2 min to upload-signed + 2-5 min for AgentCore parse + CI.
            timeout=Duration.minutes(10),
            # 1GB memory: FastAPI/uvicorn + LWA baseline ~200MB; headroom
            # for the SSE buffer + boto3 stream reads. CPU scales with
            # memory, so 1GB also halves cold-start time vs 512MB.
            memory_size=1024,
            environment={
                "AGENTCORE_AGENT_ARN": AGENTCORE_AGENT_ARN,
                "BEDROCK_REGION": "ap-northeast-2",
                "INPUT_BUCKET": INPUT_BUCKET,
                "ARTIFACTS_BUCKET": ARTIFACTS_BUCKET,
                "ALLOWED_ORIGINS": "http://localhost:5173,http://127.0.0.1:5173",
                # Auth — Lambda fetches the actual token value from Secrets
                # Manager at startup. If the env var is unset, auth is
                # disabled (dev / local convenience).
                "APP_TOKEN_SECRET_ARN": app_token_secret.secret_arn,
                # LWA configuration
                "AWS_LWA_PORT": "8080",
                "AWS_LWA_READINESS_CHECK_PATH": "/health",
                "AWS_LWA_INVOKE_MODE": "response_stream",
                # Tell Lambda to use the LWA bootstrap wrapper
                "AWS_LAMBDA_EXEC_WRAPPER": "/opt/bootstrap",
                # Ensure deps layer is on PYTHONPATH (belt + suspenders)
                "PYTHONPATH": "/opt/python:/var/task:/var/runtime:/var/lang/lib/python3.12/site-packages",
            },
        )

        # IAM: read the auth token secret
        app_token_secret.grant_read(proxy_fn)

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
                allowed_methods=[
                    lambda_.HttpMethod.GET,
                    lambda_.HttpMethod.POST,
                ],
                allowed_headers=["Content-Type", "Authorization"],
                max_age=Duration.minutes(10),
            ),
        )

        # CloudWatch alarms — fire when the proxy errors out or gets slow
        # enough to suggest timeouts. No SNS wired up yet; alarms show up
        # in the console. When we're ready to page, attach an SNS topic.
        cloudwatch.Alarm(
            self,
            "ProxyErrorsAlarm",
            metric=proxy_fn.metric_errors(period=Duration.minutes(5)),
            threshold=1,
            evaluation_periods=1,
            comparison_operator=cloudwatch.ComparisonOperator.GREATER_THAN_OR_EQUAL_TO_THRESHOLD,
            alarm_description="Proxy Lambda errored ≥1× in the last 5 min",
            treat_missing_data=cloudwatch.TreatMissingData.NOT_BREACHING,
        )
        cloudwatch.Alarm(
            self,
            "ProxyDurationP95Alarm",
            metric=proxy_fn.metric_duration(
                period=Duration.minutes(5),
                statistic="p95",
            ),
            # 120s p95 = yellow flag; real timeout is 10 min. Adjust after
            # a week of baseline observation.
            threshold=120_000,
            evaluation_periods=2,
            comparison_operator=cloudwatch.ComparisonOperator.GREATER_THAN_THRESHOLD,
            alarm_description="Proxy Lambda p95 duration > 120s (two consecutive 5-min windows)",
            treat_missing_data=cloudwatch.TreatMissingData.NOT_BREACHING,
        )

        CfnOutput(self, "ProxyFunctionUrl", value=fn_url.url)
        CfnOutput(self, "ProxyFunctionArn", value=proxy_fn.function_arn)
        # Operator uses this to fetch the token value:
        #   aws secretsmanager get-secret-value --secret-id <ARN> \
        #     --query SecretString --output text
        CfnOutput(self, "AppTokenSecretArn", value=app_token_secret.secret_arn)
