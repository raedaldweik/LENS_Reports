from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from services import llm

router = APIRouter(prefix="/api", tags=["chat"])


class QueryRequest(BaseModel):
    query: str
    conversation_history: list[dict] = []


# Suggested prompts shown as chips on a fresh conversation (bilingual AR/EN).
SUGGESTIONS = [
    {"id": "kpis",      "label": "Q1", "prompt": "أعطني أهم مؤشرات لوحة السائقين الخطرين",
     "description": "Dangerous-drivers overview KPIs"},
    {"id": "risk",      "label": "Q2", "prompt": "Who are our 10 riskiest drivers and what should we do about them?",
     "description": "Driver risk model + recommendations"},
    {"id": "offences",  "label": "Q3", "prompt": "اعرض المخالفات الأكثر تكراراً في رسم بياني",
     "description": "Top offences chart"},
    {"id": "profile",   "label": "Q4", "prompt": "اعرض البطاقة التعريفية للسائق أحمد الزعابي",
     "description": "Driver profile card lookup"},
    {"id": "forecast",  "label": "Q5", "prompt": "Run the dangerous-drivers forecast to 2030",
     "description": "Forecasting model"},
    {"id": "watchlist", "label": "Q6", "prompt": "كم سائقاً خطراً لديه بلاغات جنائية مقلقة وهو داخل الدولة حالياً؟",
     "description": "Cross-dataset priority watchlist"},
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
