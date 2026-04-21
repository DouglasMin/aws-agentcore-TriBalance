# TriBalance — Backend Init Design

**Date:** 2026-04-21
**Status:** Design (brainstormed, pending plan)
**Scope:** Phase 1 백엔드 (AgentCore Runtime + Code Interpreter + Apple Health XML 파이프라인)
**Out of scope:** 웹 UI (별도 spec), Memory/개인화, 인증, Fitbit 연동, 스트레스/HRV 축

---

## 1. Purpose

### 제품 비전 (from `docs/guide.md`)
> **"TriBalance"** — Apple Health 데이터를 올리면, 수면·운동·스트레스 3축을 분석해 주간 라이프스타일 플랜을 만들어주는 SaaS.

### 이 spec이 완성하는 것
Apple Health `export.xml` 한 파일로부터 **수면 + 활동 2축의 실제 pandas 분석**을 수행해 **주간 플랜 + 차트 아티팩트**를 생성하는 **백엔드 단독 에이전트**. 웹 UI가 붙기 전이라도 CLI/boto3 `agentcore invoke`로 전체 파이프라인을 호출·검증할 수 있다.

### 차별화 포인트 (포트폴리오 맥락)
1. AgentCore **Code Interpreter**가 주연: LLM이 pandas/matplotlib 코드를 **생성**하고 격리된 샌드박스가 **실제로 실행**함. "LLM이 지어낸 분석"이 아님을 로그·차트·이벤트 스트림으로 증명.
2. AgentCore 생태계 5개 서비스 중 3개(**Runtime · Code Interpreter · Observability**)를 1단계에서 소비. Memory/Identity는 Phase 2-3.
3. **LangGraph + LangSmith**로 그래프-레벨 관측성 확보. `bedrock_agentcore` SDK의 LangGraph OTel 계측과 병행.

---

## 2. Functional Outcomes

### 2.1 유저가 이 프로젝트 완료 시 할 수 있는 것

1. **CLI 호출**
   ```bash
   AWS_PROFILE=developer-dongik agentcore invoke --payload '{
     "s3_key": "samples/my_apple_health_export.xml",
     "week_start": "2026-04-14"
   }'
   ```
2. **실시간 이벤트 스트림** 수신 (`@app.entrypoint`가 AsyncGenerator yield). 각 노드의 시작/완료, Code Interpreter가 실행한 **실제 코드**와 **stdout**, 생성된 차트 s3 key가 순차적으로 흐름.
3. **최종 JSON 응답**: 지표(수면 평균/효율/추세, 활동 걸음·운동·칼로리), 인사이트 bullet, 주간 플랜 텍스트, 차트 S3 key 2개.
4. **S3 아티팩트 버킷**에서 `sleep_trend.png`, `activity_trend.png`를 직접 내려받아 확인.
5. **LangSmith 대시보드**에서 run 트레이스 확인 — 노드별 시간, LLM 프롬프트/응답/토큰, Code Interpreter child span의 코드·stdout.
6. **AgentCore Observability (CloudWatch)** 콘솔에서 분산 trace, latency, error rate.
7. **LLM provider 스위치**: `agentcore.json`의 `env.LLM_PROVIDER`를 `openai` ↔ `bedrock`으로 바꿔 `agentcore launch` 재배포 → 다음 invoke부터 반영. **런타임 무재배포 전환은 Phase 2**에서 AgentCore Memory `USER_PREFERENCE` 또는 DDB 조회로 `get_provider()`를 확장할 때 추가.

### 2.2 검증 체크리스트

| # | 기능 | 검증 방법 |
|---|---|---|
| 1 | XML 파싱 | `test_parse.py` — fixture XML → 예상 record 개수/필드 |
| 2 | Code Interpreter 세션 lifecycle | `test_code_interpreter.py` — start/execute/stop, 에러 재시도 |
| 3 | 수면 지표 산출 | `test_sleep.py` — fixture CSV → 평균 수면시간/효율 assertion |
| 4 | 활동 지표 산출 | `test_activity.py` — 동일 패턴 |
| 5 | LLM provider 스위처블 | 단위 테스트에서 `LLM_PROVIDER`별 factory 인스턴스 타입 확인 |
| 6 | Self-correcting 코드 루프 | 의도적 잘못된 schema 프롬프트로 1회 실패 → 재생성 성공 |
| 7 | 그래프 전체 흐름 | `test_graph.py` — 노드 mock으로 entry → END 도달 |
| 8 | 배포 | `agentcore launch` 성공 (유저 수동) |
| 9 | E2E 실 호출 | 샘플 XML S3 업로드 → invoke → JSON 수신 + S3 차트 생성 확인 |
| 10 | LangSmith 노출 | `LANGSMITH_TRACING=true` 후 대시보드에 run 확인 |

---

## 3. Architecture

### 3.1 High-level
```
┌─────────────────────────────────────────────────────────────────┐
│ Client (CLI / 다음 spec에서 웹 UI)                               │
│   agentcore invoke --payload {s3_key, week_start}                │
└────────────────────────────┬────────────────────────────────────┘
                             │ SSE 이벤트 스트림
┌────────────────────────────▼────────────────────────────────────┐
│ AgentCore Runtime  (TriBalanceAgent, Container ARM64)            │
│                                                                  │
│  BedrockAgentCoreApp (@app.entrypoint)                           │
│   └─ LangGraph StateGraph                                        │
│        ┌─ fetch_s3  ──▶ parse_xml ──┐                            │
│        │                            ▼                            │
│        │                    sleep_code_interpret ─┐              │
│        │                                          ▼              │
│        │                    activity_code_interpret              │
│        │                                          │              │
│        │                    synthesize ◀──────────┘              │
│        │                         │                               │
│        │                         ▼                               │
│        └────────────────▶  plan_generator ──▶ END                │
│                                                                  │
│  infra/code_interpreter.py ──▶ bedrock-agentcore  (sandbox)      │
│  infra/llm.py              ──▶ OpenAI / Bedrock                  │
│  infra/s3.py               ──▶ S3 (input/artifacts)              │
└─────────────────────────────────────────────────────────────────┘
                             │
           ┌─────────────────┼──────────────────┐
           ▼                 ▼                  ▼
      S3 (input)       Code Interpreter    Artifacts S3
                       (sandbox session)   (charts PNG)
                             │
                             ▼
                       LangSmith (LangGraph 자동) + CloudWatch OTel (AgentCore 자동)
```

### 3.2 주요 설계 결정

| 결정 | 선택 | 근거 |
|---|---|---|
| 프레임워크 | LangGraph | 파이프라인 흐름 명시성, `imageeditoragent`에서 검증된 패턴, LangSmith 자동 통합 |
| 빌드 타입 | Container (ARM64) | `lxml` 등 C 확장 안정성, `imageeditoragent` 패턴 복제 |
| 데이터 입력 | S3 presigned URL (key만 payload) | XML 100MB+ 대응, 프론트 재사용 |
| 파싱 위치 | **Runtime 프로세스 내부** (lxml) | 큰 원본을 sandbox에 넣지 않음. 축약 CSV만 sandbox로 보냄 |
| Code Interpreter | 기본 sandbox, 커스텀 리소스 미사용 | S3 접근 불필요 (CSV를 `writeFiles`로 직접 주입) → IAM/CDK 복잡도 제거 |
| LLM | OpenAI ⇄ Bedrock 스위처블 | `finance-ai-app`의 `infra/llm.py` 이식. 이번 spec은 env var만, DDB/Memory 기반 동적 전환은 Phase 2 |
| 관측성 | LangSmith + AgentCore Observability | LangGraph 노드 자동 추적, Code Interpreter 호출은 `@traceable`로 child span |

### 3.3 공식 레퍼런스

- AgentCore Runtime + LangGraph: [AgentCore Starter Toolkit — LangGraph Integration](https://context7.com/aws/bedrock-agentcore-starter-toolkit/llms.txt)
- Code Interpreter SDK: https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/code-interpreter-using-directly.html
- Code Interpreter 파일 ops: https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/code-interpreter-file-operations.html
- `imageeditoragent/app/ImageEditor/main.py` (sibling repo) — LangGraph on Runtime
- `finance-ai-app/financeaiapp/app/FinancialAgent/infra/llm.py` (sibling repo) — LLM provider 팩토리

---

## 4. Directory Layout

```
agentcore-code-interpreter/
├── AGENTS.md                       # 루트 가이드 (AgentCore 프로젝트 컨벤션)
├── README.md
├── docs/
│   ├── guide.md
│   └── superpowers/
│       └── specs/
│           └── 2026-04-21-tribalance-init-design.md   # (이 문서)
│
├── tribalance/                     # [backend] 이 spec의 구현 대상
│   ├── AGENTS.md
│   ├── agentcore/
│   │   ├── agentcore.json          # schema-first 선언
│   │   ├── aws-targets.json
│   │   ├── .llm-context/           # 타입 정의 (imageeditoragent에서 복사)
│   │   └── cdk/                    # 자동 생성, 편집 금지
│   ├── app/
│   │   └── TriBalanceAgent/
│   │       ├── main.py             # BedrockAgentCoreApp + @app.entrypoint
│   │       ├── graph.py            # LangGraph StateGraph 조립
│   │       ├── state.py            # TypedDict State
│   │       ├── Dockerfile          # ARM64 + uv
│   │       ├── pyproject.toml
│   │       ├── uv.lock
│   │       ├── nodes/
│   │       │   ├── __init__.py
│   │       │   ├── fetch.py
│   │       │   ├── parse.py
│   │       │   ├── sleep.py
│   │       │   ├── activity.py
│   │       │   ├── synthesize.py
│   │       │   └── plan.py
│   │       ├── infra/
│   │       │   ├── __init__.py
│   │       │   ├── llm.py          # finance-ai-app에서 이식
│   │       │   ├── code_interpreter.py
│   │       │   ├── s3.py
│   │       │   ├── logging_config.py
│   │       │   └── secrets.py
│   │       ├── prompts/
│   │       │   ├── code_synthesis_sleep.md
│   │       │   ├── code_synthesis_activity.md
│   │       │   └── plan_generator.md
│   │       └── tests/
│   │           ├── fixtures/
│   │           │   ├── export_sample.xml   # 수면+활동 40건 축약
│   │           │   ├── sleep_sample.csv
│   │           │   └── activity_sample.csv
│   │           ├── test_parse.py
│   │           ├── test_sleep.py
│   │           ├── test_activity.py
│   │           ├── test_code_interpreter.py
│   │           ├── test_llm.py
│   │           └── test_graph.py
│   └── dev.sh                      # 로컬 dev 런처
│
├── tribalance-frontend/            # [frontend, 예약만] 다음 spec에서 구현
│   └── .gitkeep
│
└── scripts/
    ├── upload_sample.sh            # 샘플 XML → S3
    └── invoke_local.sh             # agentcore invoke 예제
```

**규칙:**
- **노드 1파일=1노드**. 노드는 `infra/`만 import. 노드끼리 import 금지.
- 프롬프트는 `.md` 로 분리 (`prompts/`). 코드 안 하드코딩 금지.
- 테스트 fixture는 실 export의 40 이벤트 수준 축약본. 로직 검증 전용.

---

## 5. LangGraph State & Nodes

### 5.1 State

```python
# state.py
from typing import TypedDict, Optional, Literal

class Metrics(TypedDict):
    avg: dict                        # {"duration_hr": 6.8, ...}
    trend: Literal["up", "down", "stable"]
    chart_s3_key: str

class TriBalanceState(TypedDict, total=False):
    # input
    s3_key: str
    week_start: str                  # ISO date, 분석 주차의 월요일
    run_id: str

    # parsed
    sleep_csv: str                   # csv string, in-memory (< 1 MB typical)
    activity_csv: str
    parse_summary: dict              # {"sleep_records": 452, "activity_records": 892, "period_days": 30}

    # analysis outputs
    sleep_metrics: Metrics
    activity_metrics: Metrics
    insights: list[str]

    # final
    plan: str

    # runtime bookkeeping
    errors: list[dict]               # [{"node": "sleep", "attempt": 1, "stderr": "..."}]
```

### 5.2 노드 signatures

| 노드 | 역할 | Code Interpreter 사용 | LLM 사용 |
|---|---|---|---|
| `fetch` | S3에서 원본 XML 다운로드 → 로컬 tmp path | ❌ | ❌ |
| `parse` | lxml 스트리밍 파싱 → `sleep_csv`, `activity_csv`, `parse_summary` 채움 | ❌ | ❌ |
| `sleep` | LLM이 pandas 코드 생성 → Code Interpreter 실행 → 차트 S3 업로드 → `sleep_metrics` 채움. 실패 시 stderr 피드백 후 최대 2회 재시도 | ✅ | `analyze` |
| `activity` | 동일 구조로 활동 축 | ✅ | `analyze` |
| `synthesize` | 두 축 지표 종합 → `insights` bullet 3-5개 (LLM) | ❌ | `orchestrator` |
| `plan` | 한국어 주간 플랜 텍스트 (LLM) | ❌ | `orchestrator` |

### 5.3 엣지 (조건부 X, 선형 파이프라인)

```python
g = StateGraph(TriBalanceState)
for name in ("fetch", "parse", "sleep", "activity", "synthesize", "plan"):
    g.add_node(name, NODES[name])
g.set_entry_point("fetch")
g.add_edge("fetch", "parse")
g.add_edge("parse", "sleep")
g.add_edge("sleep", "activity")
g.add_edge("activity", "synthesize")
g.add_edge("synthesize", "plan")
g.add_edge("plan", END)
```

> 주의: 초기엔 sleep → activity 순차. 이후(Phase 1.5) `Send()`로 병렬화 가능.

### 5.4 Self-correcting 루프 (sleep/activity 노드 내부)

```python
for attempt in range(MAX_ATTEMPTS):  # 기본 3
    code = llm_generate_code(prompt, feedback=last_error)
    emit({"event": "code_generated", "node": name, "code": code, "attempt": attempt})
    result = ci.execute_code(code)
    emit({"event": "code_result", "node": name, "stdout": result["stdout"], "ok": result["ok"]})
    if result["ok"]:
        break
    last_error = result["stderr"]
else:
    raise CodeInterpreterRetryExhausted(name)
```

---

## 6. Code Interpreter Integration

### 6.1 `infra/code_interpreter.py` 인터페이스

```python
from bedrock_agentcore.tools.code_interpreter_client import CodeInterpreter
from langsmith import traceable

class CodeInterpreterWrapper:
    def __init__(self, region: str):
        self._client = CodeInterpreter(region)
        self._started = False

    def __enter__(self):
        self._client.start()
        self._started = True
        return self

    def __exit__(self, *exc):
        if self._started:
            self._client.stop()

    def write_files(self, files: dict[str, str]) -> None:
        content = [{"path": p, "text": t} for p, t in files.items()]
        self._client.invoke("writeFiles", {"content": content})

    @traceable(name="code_interpreter.execute", run_type="tool")
    def execute_code(self, code: str) -> dict:
        response = self._client.invoke("executeCode", {
            "language": "python",
            "code": code,
        })
        return self._collect_stream(response)

    def read_file(self, path: str) -> bytes:
        response = self._client.invoke("readFiles", {"paths": [path]})
        return self._extract_bytes(response)

    @staticmethod
    def _collect_stream(response) -> dict:
        stdout, stderr, files, error = [], [], [], None
        for event in response["stream"]:
            r = event.get("result", {})
            if r.get("stdout"): stdout.append(r["stdout"])
            if r.get("stderr"): stderr.append(r["stderr"])
            if r.get("files"): files.extend(r["files"])
            if r.get("error"): error = r["error"]
        return {
            "stdout": "".join(stdout),
            "stderr": "".join(stderr),
            "files": files,
            "ok": error is None and not stderr,
            "error": error,
        }
```

### 6.2 Session 라이프사이클 규약

- Runtime invocation 당 **1 session**. 노드들이 같은 wrapper 인스턴스 공유.
- `@app.entrypoint` 최상단에서 `with CodeInterpreterWrapper(region) as ci:` 블록으로 감싸서 finally 누수 방지.
- `session_timeout`: 기본 sandbox 기본값 사용 (30분). Apple Health 분석은 수 초~수십 초 예상.

### 6.3 데이터 왕복

```
Runtime 프로세스                         Code Interpreter sandbox
─────────────────                        ────────────────────────
parse.py (lxml)
  └─▶ sleep_csv (str)  ──writeFiles──▶  /sandbox/sleep.csv
      activity_csv     ──writeFiles──▶  /sandbox/activity.csv

LLM generates code    ──executeCode──▶  pd.read_csv + plt.savefig
                                        /sandbox/sleep_trend.png

                      ◀──readFiles───    /sandbox/sleep_trend.png (bytes)
s3.py upload
  └─▶ s3://tribalance-artifacts/runs/{run_id}/sleep_trend.png
```

---

## 7. LLM Factory (from `finance-ai-app`)

### 7.1 파일: `infra/llm.py`

```python
from typing import Literal
import os
from langchain_core.language_models.chat_models import BaseChatModel
from infra.secrets import get_secret

Purpose = Literal["orchestrator", "analyze"]

_DEFAULTS: dict[tuple[str, Purpose], str] = {
    ("openai", "orchestrator"): "gpt-5.4-mini",
    ("openai", "analyze"):      "gpt-5.4",
    ("bedrock", "orchestrator"): "global.anthropic.claude-haiku-4-5-20251001-v1:0",
    ("bedrock", "analyze"):      "global.anthropic.claude-opus-4-6-v1",
}

def get_provider() -> str:
    return os.environ.get("LLM_PROVIDER", "openai").lower()

def get_llm(purpose: Purpose) -> BaseChatModel:
    provider = get_provider()
    env_override = os.environ.get(f"{purpose.upper()}_MODEL")
    model = env_override or _DEFAULTS.get((provider, purpose), _DEFAULTS[("openai", purpose)])

    if provider == "openai":
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(model=model, api_key=get_secret("OPENAI_API_KEY"), max_retries=2)
    if provider == "bedrock":
        from langchain_aws import ChatBedrockConverse
        return ChatBedrockConverse(
            model=model,
            region_name=os.environ.get("BEDROCK_REGION", "us-west-2"),
            max_retries=2,
        )
    raise ValueError(f"Unknown LLM_PROVIDER: {provider}")
```

### 7.2 Phase 2 확장 포인트
- `get_provider()` 의 내부 구현을 DDB/AgentCore Memory `USER_PREFERENCE` 조회로 교체하면 유저별 런타임 스위치 가능. 인터페이스는 동일.

---

## 8. AgentCore Schema (`agentcore.json`)

```json
{
  "name": "tribalance",
  "agents": [
    {
      "name": "TriBalanceAgent",
      "description": "Apple Health 데이터 분석 + 주간 플랜 생성 (수면+활동 2축)",
      "entrypoint": "main.py",
      "codeLocation": "./app/TriBalanceAgent",
      "buildType": "Container",
      "networkMode": "PUBLIC",
      "runtimeVersion": "PYTHON_3_12",
      "env": {
        "LLM_PROVIDER": "openai",
        "BEDROCK_REGION": "us-west-2",
        "ARTIFACTS_S3_BUCKET": "tribalance-artifacts",
        "LANGSMITH_TRACING": "true",
        "LANGSMITH_PROJECT": "TriBalance"
      }
    }
  ],
  "memories": [],
  "credentials": [
    { "name": "OPENAI_API_KEY", "type": "apiKey" },
    { "name": "LANGSMITH_API_KEY", "type": "apiKey" }
  ]
}
```

`aws-targets.json`: region `us-west-2`, account/stack prefix는 유저 환경에 따라.

### IAM 권한 (배포 시 필요)
- Runtime execution role: S3 input 버킷 `GetObject`, artifacts 버킷 `PutObject`, Bedrock `InvokeModel`, Code Interpreter `InvokeCodeInterpreter / StartCodeInterpreterSession / StopCodeInterpreterSession`
- Secrets Manager: `OPENAI_API_KEY`, `LANGSMITH_API_KEY` 읽기

---

## 9. Event Stream Contract

`@app.entrypoint`가 yield하는 이벤트 스키마 (다음 spec의 UI가 소비).

```typescript
type Event =
  | { event: "run_started"; run_id: string; period: string }
  | { event: "node_start"; node: NodeName }
  | { event: "node_end"; node: NodeName; duration_ms: number }
  | { event: "parse_summary"; sleep_records: number; activity_records: number }
  | { event: "code_generated"; node: "sleep" | "activity"; code: string; attempt: number }
  | { event: "code_result"; node: "sleep" | "activity"; stdout: string; ok: boolean }
  | { event: "artifact"; node: string; s3_key: string; content_type: "image/png" }
  | { event: "metrics"; node: "sleep" | "activity"; payload: Metrics }
  | { event: "insights"; items: string[] }
  | { event: "plan"; text: string }
  | { event: "error"; node?: string; message: string }
  | { event: "complete"; report: FinalReport }
```

UI spec에서 이 이벤트 스트림을 SSE로 소비하기로 전제.

---

## 10. Testing Strategy

### 10.1 단위 테스트
- `test_parse.py`: fixture `export_sample.xml` → `sleep_csv`, `activity_csv` 생성. record 개수, 날짜 필드 단조성 확인.
- `test_sleep.py` / `test_activity.py`: fixture CSV + mock LLM (고정 코드 문자열 반환) + **Code Interpreter를 stub**으로 대체해 graph-level 로직만 검증. 실 SDK는 통합 테스트에서.
- `test_code_interpreter.py`: wrapper의 stream parsing 로직 단위 테스트 (fake response).
- `test_llm.py`: `LLM_PROVIDER` env 별 factory가 올바른 chat 클래스 인스턴스를 반환하는지.
- `test_graph.py`: 모든 노드 stub → entry → END 도달 + state 필드 flow.

### 10.2 통합 테스트 (`tests/integration/`, 수동)
- 실 AWS credential 필요.
- 샘플 XML S3 업로드 → `agentcore invoke` → JSON 수신 + S3 차트 확인.
- CI에서는 스킵 (AWS 비용).

### 10.3 커버리지 목표
- `nodes/`, `infra/`: ≥ 80 %
- `main.py`, `graph.py`: ≥ 70 %

---

## 11. Deployment & Local Dev

### 11.1 로컬
```bash
# 최초 1회
cd tribalance/app/TriBalanceAgent
uv sync

# 로컬 실행 (agentcore dev가 컨테이너 빌드 + 볼륨 마운트)
cd tribalance
./dev.sh   # = AWS_PROFILE=developer-dongik agentcore dev
```

### 11.2 배포 (유저 수동)
```bash
cd tribalance
AWS_PROFILE=developer-dongik agentcore launch
```

### 11.3 의존 관리
- `uv` + `pyproject.toml` + `uv.lock`. `uv.lock` 항상 커밋.
- 주요 deps: `bedrock-agentcore>=1.6`, `langgraph`, `langchain-openai`, `langchain-aws`, `langsmith`, `lxml`, `boto3`.

---

## 12. Risks & Open Questions

| # | 항목 | 완화 |
|---|---|---|
| 1 | Apple Health `export.xml`가 실제로 100MB+ — Runtime Container 메모리/디스크 한계 | lxml `iterparse` 스트리밍 파싱. 중간 CSV만 메모리 유지 |
| 2 | LLM이 CSV 컬럼명/스키마를 틀리게 쓴 pandas 코드 생성 | 프롬프트에 컬럼 schema 명시 + self-correcting 루프 (stderr 피드백) + 시스템 프롬프트에 금지 패턴 명시 |
| 3 | Code Interpreter 세션 누수 (stop 실패 시 30분 점유) | `with` 블록 + 노드 외부에서 예외 발생해도 finally 보장 |
| 4 | LangSmith 트래픽 증가 → 비용 | `LANGSMITH_TRACING=false` 로 dev 중 토글 가능 |
| 5 | OpenAI 키 관리 | AgentCore Credentials(Secrets Manager) — `agentcore.json`에 선언 |
| 6 | `bedrock-agentcore` Python SDK API는 2025년 말부터 변경 잦음 | `uv.lock` 고정, SDK 버전업 시 smoke test 필수 |

### Open (다음 spec에서 결정)
- 웹 UI의 정확한 SSE 컨슈머 형태 (React hook 구조, 차트 렌더 라이브러리)
- 인증 (Phase 1.5에서도 필요할지)
- 샘플 XML 공유 방식 (유저가 자기 Apple Health export를 올릴지, 제공 샘플을 쓸지)

---

## 13. Sibling Repo References

이 스펙이 베끼는/참고하는 패턴:

| 대상 | 용도 |
|---|---|
| `per-projects/agentcore-service/imageeditoragent/app/ImageEditor/` | LangGraph on AgentCore Runtime 구조, `main.py` entrypoint, Dockerfile |
| `per-projects/agentcore-service/imageeditoragent/agentcore/` | `.llm-context/` 스키마 타입, `agentcore.json` 작성 규칙 |
| `per-projects/finance-ai-app/financeaiapp/app/FinancialAgent/infra/llm.py` | LLM provider 팩토리 전체 |
| `per-projects/finance-ai-app/financeaiapp/app/FinancialAgent/infra/secrets.py` | Secrets Manager 접근 유틸 |

---

## 14. Out of Scope (명시적 제외)

- 웹 UI (별도 spec: `2026-04-21-tribalance-ui-design.md`, 이 spec 직후 작성 예정)
- 사용자 인증 (Cognito 등 — Phase 3)
- AgentCore Memory 통합 (Phase 2)
- AgentCore Identity / Fitbit OAuth (Phase 3)
- 스트레스/HRV 분석 축 (Phase 2)
- 주간 체크인 흐름 / 과거 플랜 이행률 비교 (Phase 2)
- 멀티테넌트 데이터 격리 (Phase 3)
- 비용/쿼터 모니터링 대시보드 (Phase 3)
