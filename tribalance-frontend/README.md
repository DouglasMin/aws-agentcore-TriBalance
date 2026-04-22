# TriBalance Frontend

ATLAS design — mission-control / data-wall aesthetic for the Apple Health weekly analysis demo. Pure Vite + React + TypeScript, no heavy UI library. The only third-party runtime deps are `react`, `react-dom`, `recharts`, and `zustand`.

## Setup

```bash
pnpm install
cp .env.example .env.local
# edit .env.local: set VITE_PROXY_URL to the deployed tribalance-proxy Function URL
```

## Dev

```bash
pnpm dev
# http://localhost:5173
```

## Typecheck / Build

```bash
pnpm typecheck
pnpm build
```
