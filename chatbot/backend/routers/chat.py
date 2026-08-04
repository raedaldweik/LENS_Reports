from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from services import llm

router = APIRouter(prefix="/api", tags=["chat"])


class QueryRequest(BaseModel):
    query: str
    conversation_history: list[dict] = []


# Suggested prompts shown as chips on a fresh conversation.
SUGGESTIONS = [
    {"id": "kpis",      "label": "Q1", "prompt": "How is the operation doing this week? Give me the key numbers.",
     "description": "Operational dashboard KPI pulse"},
    {"id": "hotspots",  "label": "Q2", "prompt": "Show the top violation hotspot zones as a chart",
     "description": "Performance dashboard zone analysis"},
    {"id": "forecast",  "label": "Q3", "prompt": "Run the 14-day alert volume forecast — do we need more staff?",
     "description": "Forecasting model"},
    {"id": "bottleneck", "label": "Q4", "prompt": "Where is the bottleneck in our alert handling workflow?",
     "description": "Process mining / bottleneck model"},
    {"id": "risk",      "label": "Q5", "prompt": "Who are our highest-risk drivers and what should we do about them?",
     "description": "Driver risk model + recommendations"},
    {"id": "staff",     "label": "Q6", "prompt": "Compare operator performance — who is breaching SLA the most?",
     "description": "Staff dashboard operator metrics"},
]


@router.post("/query")
def query(req: QueryRequest) -> dict:
    q = (req.query or "").strip()
    if not q:
        raise HTTPException(status_code=400, detail="Empty query")
    try:
        result = llm.run_agent(q, req.conversation_history)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Agent error: {e}")
    result["query_id"] = f"q_{uuid.uuid4().hex[:12]}"
    return result


@router.get("/scenarios")
def scenarios() -> list[dict]:
    return SUGGESTIONS
