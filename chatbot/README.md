# RTA Smart Monitoring Assistant

An agentic data-analysis chatbot over the three monitoring dashboards in this repo:

| Scope | Dashboard | Data |
|---|---|---|
| Driver violations, risk scores, hotspots | `performance.html` | `violations.csv` (16.5K rows) |
| Alerts, SLA compliance, resolution times | `operational.html` | `alerts.csv` (8.5K rows) |
| Operator workload and performance | `staff.html` | `alerts.csv` + 24-operator roster |

It can also run the three analytical models behind the dashboards — **forecasting** (14-day
alert volume), **bottleneck / process mining** (10-stage alert workflow), and **driver risk**
(0–10 scoring) — generate charts, and give operational recommendations. Questions outside
this scope are politely declined.

## Architecture

Same pattern as the Health-repo assistant:

- **Backend** (`backend/`) — FastAPI + Claude with tool-use. Three tools: `fleet_query`
  (structured pandas queries over the CSVs), `run_model` (forecast / bottleneck / risk) and
  `render_chart` (emits a chart spec). Responses carry `answer` (markdown), `charts`
  (Recharts specs) and `trace` (reasoning steps).
- **Frontend** (`frontend/`) — React 19 + Vite + Tailwind + Recharts. Glass-morphism chat UI
  re-skinned to RTA branding (Manrope, RTA red), with conversation sidebar, suggestion chips,
  dynamic charts and a collapsible agent-reasoning panel.

## Run locally

```bash
# Backend (terminal 1)
cd chatbot/backend
pip install -r requirements.txt
cp .env.example .env          # put your ANTHROPIC_API_KEY in .env
uvicorn main:app --reload --port 8000

# Frontend (terminal 2)
cd chatbot/frontend
npm install
npm run dev                   # http://localhost:5173 (proxies /api to :8000)
```

Port 8000 already taken? Run the backend on any other port and point the dev proxy at it:

```bash
uvicorn main:app --reload --port 8010              # backend
VITE_API_PORT=8010 npm run dev                     # frontend
```

The backend looks for `alerts.csv` / `violations.csv` at the repo root; if they aren't found
it falls back to the published copies at `https://raedaldweik.github.io/reports/`.

## Single-container deployment

```bash
# From the repo root
docker build -f chatbot/Dockerfile -t rta-assistant .
docker run -p 8000:8000 -e ANTHROPIC_API_KEY=sk-ant-... rta-assistant
```

The container builds the frontend and serves it from FastAPI at `/`, with the API under
`/api/*` (health check: `GET /api/health`).
