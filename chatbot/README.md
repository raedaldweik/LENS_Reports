# Dubai Police Smart Assistant — المساعد الذكي

An agentic data-analysis chatbot for the Dubai Police **Security Analytics & Forecast
Center** (مركز التحليل والتنبؤ الأمني), grounded in the dangerous-drivers dashboards:

| Dashboard page | Data |
|---|---|
| Dangerous drivers overview (المخالفات والسائقون الخطرون) | `TRF_DANGEROUS_JOIN_V3.csv` — 2,462 violations, 750 drivers |
| Driver profile card (البطاقة التعريفية للسائق الخطر) | joined view of all three datasets per driver |
| Criminal reports (البلاغات الجنائية) | `TRF_DRIVER_CID_CASES.csv` — 1,105 rows, 612 reports |
| Movements (التحركات) | `TRF_DRIVER_MOVEMENTS_V2.csv` — 750 persons, 4,808 vehicles |

All three datasets join on the traffic file number (رقم الملف المروري / `TRAFFIC_NO`).

It can also run the three analytical models behind the dashboards — **forecasting**
(a faithful port of the dashboard's Data-Driven-Content forecast card: OLS linear trend
on distinct drivers per registration year, partial final year dropped, 95% prediction
interval — same headline as the dashboard, ~700 by 2030, 1,767 on the risk list, 53.5%
high-risk), **risk** (0–1 scoring = avg offence score/100; fleet average 0.57) and
**segmentation** (danger category × demographic profiles) — plus a cross-dataset
**watchlist** (dangerous drivers with concerning criminal reports currently inside the
country), generate charts, and give operational recommendations. It answers in the
language of the question (Arabic or English). Questions outside this scope are politely
declined.

## Architecture

- **Backend** (`backend/`) — FastAPI + Claude with tool-use. Three tools: `police_query`
  (structured pandas queries over the CSVs, incl. per-driver profile cards), `run_model`
  (forecast / risk / segmentation / watchlist) and `render_chart` (emits a chart spec).
  Responses carry `answer` (markdown), `charts` (Recharts specs) and `trace` (reasoning steps).
- **Frontend** (`frontend/`) — React 19 + Vite + Tailwind + Recharts. Dark-green
  glass-morphism chat UI matching the dashboards (Manrope + IBM Plex Sans Arabic),
  bilingual suggestion chips, conversation sidebar, dynamic charts and a collapsible
  agent-reasoning panel.

> **Branding note:** the header uses a neutral shield badge (`frontend/public/badge.svg`)
> plus a text wordmark. To show the official emblem, drop it in as
> `frontend/public/police.png` — the header picks it up automatically.

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

The backend looks for the three `TRF_*.csv` files at the repo root (override with `DATA_DIR`).

## Single-container deployment

```bash
# From the repo root
docker build -f chatbot/Dockerfile -t police-assistant .
docker run -p 8000:8000 -e ANTHROPIC_API_KEY=sk-ant-... police-assistant
```

The container builds the frontend and serves it from FastAPI at `/`, with the API under
`/api/*` (health check: `GET /api/health`). See `DEPLOY.md` for Railway.
