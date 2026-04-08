"""
/query endpoint — main AI orchestration entry point.
Accepts natural language queries and routes them through
the LangGraph orchestrator.
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from loguru import logger

from app.agents.orchestrator import OrchestratorAgent


router = APIRouter(prefix="/query", tags=["Query"])

# Module-level singleton (initialised on first request to avoid cold-start cost)
_orchestrator: OrchestratorAgent | None = None


def _get_orchestrator() -> OrchestratorAgent:
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = OrchestratorAgent()
    return _orchestrator


class QueryRequest(BaseModel):
    user_id: str
    query: str

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "user_id": "user_abc123",
                    "query": "What should I do today?",
                }
            ]
        }
    }


class QueryResponse(BaseModel):
    user_id: str
    query: str
    route: str
    answer: str
    raw_agent_output: str


@router.post("/", response_model=QueryResponse, summary="Ask the AI assistant")
async def query_ai(request: QueryRequest) -> dict[str, Any]:
    """
    Send a natural-language query to the multi-agent system.

    The orchestrator automatically routes the query to the appropriate
    sub-agent (Task, Calendar, Notes, or Risk) and returns a synthesised answer.

    **Example queries:**
    - "What should I do today?"
    - "Show my delayed tasks"
    - "Schedule a meeting for tomorrow morning"
    - "Am I overloaded this week?"
    - "Find my notes about project X"
    """
    try:
        orchestrator = _get_orchestrator()
        result = await orchestrator.query(
            user_id=request.user_id,
            query=request.query,
        )
        return result
    except Exception as exc:
        logger.error(f"[/query] Error: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))
