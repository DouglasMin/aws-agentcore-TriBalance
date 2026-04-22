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

        proxy_fn = lambda_.Function(
            self,
            "ProxyFunction",
            runtime=lambda_.Runtime.PYTHON_3_12,
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
            timeout=Duration.minutes(5),
            memory_size=512,
            environment={
                "AGENTCORE_AGENT_ARN": AGENTCORE_AGENT_ARN,
                "BEDROCK_REGION": "ap-northeast-2",
                "INPUT_BUCKET": INPUT_BUCKET,
                "ARTIFACTS_BUCKET": ARTIFACTS_BUCKET,
                "ALLOWED_ORIGINS": "http://localhost:5173,http://127.0.0.1:5173",
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

        CfnOutput(self, "ProxyFunctionUrl", value=fn_url.url)
        CfnOutput(self, "ProxyFunctionArn", value=proxy_fn.function_arn)
