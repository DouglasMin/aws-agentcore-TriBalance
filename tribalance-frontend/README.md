# TriBalance Frontend (ATLAS)

Vite + React + TypeScript. ATLAS design — mission-control / data-wall aesthetic. No heavy UI library; only `react`, `react-dom`, `recharts`, `zustand`.

## Setup

```bash
pnpm install
cp .env.example .env.local
# edit .env.local — VITE_PROXY_URL = the Function URL output by `cdk deploy`
```

## Scripts

```bash
pnpm dev         # http://localhost:5173
pnpm typecheck   # strict tsc -b
pnpm build       # production bundle to dist/
pnpm preview     # serve dist/
```

## Architecture

- **Events** (`src/store/events.ts`) mirror what `tribalance/app/TriBalanceAgent/main.py` and `nodes/_codegen.py` emit.
- **Store** (`src/store/runStore.ts`) is a single `zustand` slice that reduces every `AgentEvent` into UI state (node status map, sleep/activity metrics, series, code attempts, insights, plan).
- **Transport** (`src/hooks/useSSE.ts`) POSTs the invoke payload to the proxy and parses SSE frames off the `ReadableStream` — not `EventSource`, because EventSource is GET-only.
- **Layout** (`src/components/Panel.tsx` + `src/styles/atlas.css`) is a 12-column grid with one `Panel` primitive that every zone (A-01, B-01, C-01, ...) wraps.

## Panels (maps 1:1 to the ATLAS mockup)

| Zone | Component | Event driving it |
|---|---|---|
| A-01 ~ A-04 | `VitalPanel` | `metrics` (sleep, activity) |
| B-01 | `PipelinePanel` | `run_started` / `node_end` / `error` |
| C-01 | `CodePanel` | `code_generated`, `code_result` |
| D-01 / D-02 | `ChartPanel` (recharts) | `parsed_series` |
| E-01 | `InsightsPanel` | `complete.report.insights` |
| F-01 | `PlanPanel` | `complete.report.plan` |
| (in B-01) | `Upload` | — (triggers `/upload-url` + `/invoke`) |

## Design Origin

The palette, typography, and panel chrome are all ported from `mockups/option-c-atlas.html`. Open that file in a browser to see the reference the real UI matches.
