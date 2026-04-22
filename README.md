# aws-agentcore-TriBalance

> **TriBalance** — Apple Health 데이터를 기반으로 수면·운동·스트레스 3축을 분석해 주간 라이프스타일 플랜을 생성하는 AI 헬스 코치.
> AWS **AgentCore Runtime + Code Interpreter** 위에서 **LangGraph + LangSmith** 로 구현되는 데이터 분석 에이전트.

## Status

| Phase | Scope | State |
|---|---|---|
| 1 — 백엔드 | Runtime + Code Interpreter + XML 파서 + 수면/활동 분석 + 주간 플랜 | **✅ Deployed** (`runtime/TriBalanceAgent-jXn0PKFg4F`) |
| 1.5 — 웹 UI + 프록시 | Vite/React ATLAS UI, Lambda Function URL (SSE + presigned S3), drag-drop 업로드 | **✅ Code complete · CDK 배포 대기** |
| 2 — 코칭 연속성 | AgentCore Memory, 체크인 흐름, 스트레스/HRV 축 | 미착수 |
| 3 — 멀티유저 SaaS | Cognito, AgentCore Identity (Fitbit OAuth), 멀티테넌트, 인증 하드닝 | 미착수 |

## 핵심 차별화

1. **AgentCore Code Interpreter 주연.** LLM이 생성한 pandas 코드를 격리 샌드박스에서 **실제로 실행** → 프론트에 그 코드와 stdout이 실시간 스트리밍으로 보임.
2. **LangGraph + LangSmith**로 그래프-레벨 관측성. AgentCore Observability(OTel)와 병행.
3. **OpenAI ⇄ Bedrock Claude 스위처블** LLM provider (`finance-ai-app` 패턴 이식).
4. **ATLAS UI** — mission-control / 데이터월 디자인. 12-col grid, 좌표 ID(A-01, C-01 등), 라이브 timecode.

## Repository Layout

```
agentcore-code-interpreter/
├── docs/                       # specs, plans, guide
├── mockups/                    # Phase 1.5 UI 디자인 (HTML)
├── tribalance/                 # AgentCore Runtime 에이전트 (Python)
│   ├── agentcore/              #   schema-first config (agentcore.json)
│   └── app/TriBalanceAgent/    #   LangGraph · nodes · Code Interpreter 래퍼
├── tribalance-proxy/           # Lambda Function URL (Python + CDK)
│   ├── infra/stack.py          #   CDK: Lambda + FunctionURL + IAM
│   └── handler/                #   SSE streaming invoke + presigned URLs
└── tribalance-frontend/        # Vite + React + TS (ATLAS UI)
    ├── src/components/         #   Panel, Topbar, Vital, Pipeline, Code, Chart, Insights, Plan, Upload
    ├── src/hooks/useSSE.ts     #   fetch + ReadableStream SSE consumer
    └── src/store/              #   zustand store + event types
```

## Quick Start

### Backend (이미 배포됨)

```bash
cd tribalance
source .venv/bin/activate
# 호출 테스트:
AWS_PROFILE=developer-dongik agentcore invoke '{
  "s3_key": "samples/export_sample.xml",
  "week_start": "2026-04-06"
}'
```

### Lambda Proxy (1회 배포 필요)

```bash
cd tribalance-proxy
uv sync --extra dev

# 첫 배포만 bootstrap 필요
AWS_PROFILE=developer-dongik uv run cdk bootstrap aws://612529367436/ap-northeast-2

# 배포
AWS_PROFILE=developer-dongik uv run cdk deploy

# 출력값에서 ProxyFunctionUrl 복사 → tribalance-frontend/.env.local 에 VITE_PROXY_URL
```

### Frontend (로컬 개발)

```bash
cd tribalance-frontend
pnpm install
cp .env.example .env.local
# .env.local 열어서 VITE_PROXY_URL = 위에서 받은 Function URL

pnpm dev
# http://localhost:5173
```

## End-to-End 시연 흐름

1. 브라우저 → `http://localhost:5173`
2. Apple Health `export.xml` 드래그-드롭 (또는 "RUN SAMPLE" 버튼으로 내장 샘플 사용)
3. 프론트가 Lambda `/upload-url`로 presigned PUT → 직접 S3 업로드
4. 프론트가 Lambda `/invoke` POST → AgentCore Runtime SSE stream 시작
5. 이벤트별 UI 갱신:
   - `parsed_series` → D-01/D-02 차트 즉시 렌더 (recharts)
   - `code_generated` → C-01 패널에 Python 코드 실시간 표시 (구문 하이라이트 + 카렛)
   - `code_result` → STDOUT 박스에 METRICS_JSON · exitCode
   - `metrics` → A-01~04 KPI 카운트업
   - `complete` → E-01 인사이트, F-01 한국어 플랜

## AWS Config

- Region: `ap-northeast-2`
- Account: `612529367436`
- Profile: `developer-dongik`
- Secrets (Secrets Manager): `OPENAI_API_KEY`, `LANGSMITH_API_KEY`
- Agent ARN: `arn:aws:bedrock-agentcore:ap-northeast-2:612529367436:runtime/TriBalanceAgent-jXn0PKFg4F`

## License

TBD
