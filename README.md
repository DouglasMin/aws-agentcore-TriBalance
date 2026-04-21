# aws-agentcore-TriBalance

> **TriBalance** — Apple Health 데이터를 기반으로 수면·운동·스트레스 3축을 분석해 주간 라이프스타일 플랜을 생성하는 AI 헬스 코치.
> AWS **AgentCore Runtime + Code Interpreter** 위에서 **LangGraph + LangSmith** 로 구현되는 데이터 분석 에이전트.

## Status

| Phase | Scope | State |
|---|---|---|
| 1 (이 리포) — 백엔드 | Runtime + Code Interpreter + Apple Health XML 파서 + 수면/활동 2축 분석 + 주간 플랜 | **Design complete** — `docs/superpowers/specs/2026-04-21-tribalance-init-design.md` |
| 1.5 — 웹 UI | 업로드 UI, SSE 이벤트 렌더러, 차트 뷰어 | 다음 spec |
| 2 — 코칭 연속성 | AgentCore Memory, 체크인 흐름, 스트레스/HRV 축 | 미착수 |
| 3 — 멀티유저 SaaS | Cognito, AgentCore Identity (Fitbit OAuth), 멀티테넌트 | 미착수 |

## 핵심 차별화

1. **AgentCore Code Interpreter**를 주연으로. LLM이 생성한 pandas/matplotlib 코드를 격리 샌드박스에서 **실제 실행** → "LLM이 지어낸 분석"이 아님을 로그/차트/이벤트 스트림으로 증명.
2. **LangGraph + LangSmith** 로 그래프-레벨 관측성. `bedrock_agentcore` SDK의 LangGraph OTel 계측과 병행.
3. **LLM provider 스위처블** (OpenAI ⇄ Bedrock Claude). `finance-ai-app` 패턴 이식.

## Repository Layout

```
agentcore-code-interpreter/
├── docs/
│   ├── guide.md                 # 프로젝트 비전 / Phase 로드맵
│   └── superpowers/specs/       # brainstormed design docs
├── tribalance/                  # backend (이 리포의 구현 대상)
└── tribalance-frontend/         # frontend (다음 spec 예약)
```

## Local Dev

```bash
# 최초 1회
cd tribalance/app/TriBalanceAgent
uv sync

# 로컬 실행
cd tribalance
./dev.sh
```

## Deploy

```bash
cd tribalance
AWS_PROFILE=developer-dongik agentcore launch
```

## License

TBD
