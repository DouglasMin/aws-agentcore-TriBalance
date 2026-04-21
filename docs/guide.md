질문은 여기까지입니다. 스코프가 확정됐습니다. 정리해드리겠습니다.

---

## 🎯 최종 프로젝트 스코프

> **"AI 헬스 코치"** — Apple Health/Fitbit 데이터를 업로드하거나 연동하면, 수면·운동·스트레스 3축을 분석해 주간 라이프스타일 플랜을 만들어주는 SaaS

### 프로젝트명 후보
1. **TriBalance** — 3축(수면/운동/스트레스) 균형 직관적
2. **Homeostasis** — 항상성, 의학 톤
3. **Pulse Coach** — 쉽고 기억하기 쉬움

---

## 🧩 AgentCore 서비스 매핑 — **5개 서비스 활용**

| 서비스 | Phase | 역할 |
|---|---|---|
| **Runtime** | 1 | 에이전트 호스팅 (Strands or LangGraph) |
| **Code Interpreter** ⭐ | 1 | pandas로 데이터 파싱·통계·matplotlib 차트 생성 |
| **Memory** | 2 | 유저별 코칭 히스토리·선호 장기 기억 |
| **Identity** | 3 | Cognito 로그인 + Fitbit/Garmin OAuth 토큰 자동 주입 |
| **Observability** | 1 (자동) | 토큰 사용량, latency, 코칭 품질 모니터링 |

Gateway는 Phase 3+에서 Fitbit API를 MCP tool화할 때 선택적으로 추가.

---

## 🗺️ Phase 로드맵

### **Phase 1 (Week 1) — MVP**
- Next.js 프론트 (업로드 UI + 차트 뷰어)
- Apple Health XML 파서 Lambda
- AgentCore Runtime + Code Interpreter 연동
- 기본 분석: 평균 수면시간, 활동량, HRV 추세
- "이번 주 플랜 생성" 1개 시나리오
- **→ 여기까지가 진짜 데모 가능한 최소 단위**

### **Phase 2 (Week 2) — 코칭 연속성**
- Memory 연동 (유저 목표·선호·과거 플랜 이행률)
- 주간 체크인 흐름 ("지난주 플랜 어땠나요?")
- What-if 시뮬레이션 ("주 3회 대신 5회 운동하면?")

### **Phase 3 (Week 3-4) — 멀티유저 SaaS**
- Cognito 로그인
- AgentCore Identity로 Fitbit OAuth 자동 연동
- 멀티테넌트 데이터 격리
- CloudWatch 대시보드 공개

---

## 🎬 핵심 시연 시나리오 (면접/블로그용)

> **시나리오**: Apple Health XML 업로드 → 에이전트가 실시간으로 Code Interpreter에서 pandas 코드를 생성·실행 → "지난 30일 수면 효율 78%, 활동량 권장치의 62%, 평일 HRV가 주말보다 23% 낮음" 리포트 + 차트 + "이번 주 플랜" 생성

**임팩트 포인트**: 화면에 생성된 Python 코드가 스트리밍으로 보이고, 실행 결과 차트가 바로 렌더링됨. "LLM이 지어낸 분석"이 아니라 **실제로 돌린 분석**임을 시각적으로 증명.

---

## 📝 기술 블로그 글감 (4편 확보)

1. "AgentCore Code Interpreter로 '진짜 실행하는' 데이터 분석 에이전트 만들기"
2. "Next.js + AgentCore Runtime 풀스택 배포 가이드"
3. "AgentCore Memory로 연속적인 코칭 에이전트 구현"
4. "AgentCore Identity로 Fitbit OAuth 3LO 안전하게 처리하기"

---

## ✨ 포트폴리오 차별화 포인트

- **"격리 실행의 가치를 제대로 보여주는 프로젝트"** — 국내 블로그 글이 거의 없음
- **AgentCore 5개 서비스 통합 사례** — 단일 서비스 튜토리얼은 많지만 5개를 엮은 사례는 드뭄
- **실사용자 시연 가능** — 본인 Apple Health 데이터로 데모 가능
- **의료 도메인 경험 + Claude Code/AgentCore 최신 스택** — 희소 조합
