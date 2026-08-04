"""
RTA Smart Monitoring Assistant — FastAPI backend.

Local dev:
    cd chatbot/backend && uvicorn main:app --reload --port 8000

Production (Docker, built from the repo root):
    uvicorn main:app --host 0.0.0.0 --port $PORT
    Frontend is pre-built at ../frontend/dist and served from "/".

Env vars:
    ANTHROPIC_API_KEY — enables chat with Claude tool-use (required for answers)
    MODEL             — override default model name
    DATA_DIR          — override location of alerts.csv / violations.csv
    PORT              — serving port
"""
from __future__ import annotations

import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

load_dotenv()

from routers import chat
from services import data as data_service


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Warm the CSV caches so the first request isn't slow."""
    for ds in data_service.DATASETS:
        try:
            df = data_service._load(ds)
            print(f"✓ Loaded {len(df)} rows from {ds}.csv (latest: {data_service.data_now(ds).date()})")
        except Exception as e:
            print(f"⚠ Could not load {ds}.csv: {e}")
    has_key = bool(os.getenv("ANTHROPIC_API_KEY"))
    print(f"✓ Mode: {'LLM (tool-use enabled)' if has_key else 'No API key — chat disabled'}")
    yield


app = FastAPI(
    title="RTA Smart Monitoring Assistant",
    description="Agentic data-analysis chatbot over the Performance, Operational and Staff dashboards",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat.router)


@app.get("/api/health")
def health() -> dict:
    has_key = bool(os.getenv("ANTHROPIC_API_KEY"))
    return {
        "status": "ok",
        "mode": "llm" if has_key else "no-key",
        "agents": ["fleet_agent", "forecast_engine", "process_mining", "risk_model", "analytics_agent"],
    }


# ─── Static frontend (Vite build) ────────────────────
FRONTEND_DIST = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "frontend", "dist"))

if os.path.isdir(FRONTEND_DIST):
    assets_dir = os.path.join(FRONTEND_DIST, "assets")
    if os.path.isdir(assets_dir):
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

    @app.get("/{filename:path}")
    def serve_spa(filename: str):
        if filename.startswith("api/"):
            return {"error": "not found"}, 404
        candidate = os.path.join(FRONTEND_DIST, filename)
        if os.path.isfile(candidate):
            return FileResponse(candidate)
        return FileResponse(os.path.join(FRONTEND_DIST, "index.html"))

    print(f"✓ Serving frontend from {FRONTEND_DIST}")
else:
    @app.get("/")
    def root() -> dict:
        return {
            "service": "RTA Smart Monitoring Assistant",
            "status": "operational (dev mode — no frontend build found)",
            "hint": "run 'npm run build' in chatbot/frontend, or use the Vite dev server on :5173",
        }
