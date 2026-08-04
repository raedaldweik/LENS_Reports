from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from services import llm

router = APIRouter(prefix="/api", tags=["chat"])


class QueryRequest(BaseModel):
    query: str
    conversation_history: list[dict] = []


# The four category cards on the empty state (icon/color are rendered by the frontend).
SUGGESTIONS = [
    {"id": "reports", "icon": "report", "color": "green",
     "category": "تقارير وملخصات",
     "prompt": "لخّص لي حالة لوحة السائقين الخطرين الآن مع أهم المؤشرات"},
    {"id": "query", "icon": "search", "color": "blue",
     "category": "استعلام عن البيانات",
     "prompt": "أظهر جميع الأشخاص من الهند الذين غادروا الدولة"},
    {"id": "alerts", "icon": "alert", "color": "amber",
     "category": "تنبيهات وأنماط",
     "prompt": "كم سائقاً خطراً لديه بلاغات جنائية مقلقة وهو داخل الدولة حالياً؟"},
    {"id": "models", "icon": "spark", "color": "purple",
     "category": "التنبؤ والنماذج",
     "prompt": "شغّل نموذج التنبؤ لأعداد السائقين الخطرين حتى 2030 واعرضه بيانياً"},
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
