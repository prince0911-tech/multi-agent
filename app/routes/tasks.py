"""
/tasks endpoints — full CRUD for task management.
"""
from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from loguru import logger

from app.tools import (
    create_task, get_tasks, update_task, delete_task,
    get_overdue_tasks, score_and_update_priority,
)


router = APIRouter(prefix="/tasks", tags=["Tasks"])


# ── Request / Response schemas ────────────────────────────────────────────────

class CreateTaskRequest(BaseModel):
    user_id: str
    title: str
    description: str = ""
    priority: str = "medium"
    importance: int = 5
    deadline: Optional[str] = None
    assigned_to: Optional[str] = None
    tags: list[str] = []

    model_config = {
        "json_schema_extra": {
            "examples": [{
                "user_id": "user_abc123",
                "title": "Prepare quarterly report",
                "description": "Compile Q3 financial data",
                "priority": "high",
                "importance": 8,
                "deadline": "2024-07-15T17:00:00",
                "tags": ["finance", "reports"],
            }]
        }
    }


class UpdateTaskRequest(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    priority: Optional[str] = None
    importance: Optional[int] = None
    deadline: Optional[str] = None
    assigned_to: Optional[str] = None
    tags: Optional[list[str]] = None


# ── Endpoints ──────────────────────────────────────────────────────────────────

@router.post("/", summary="Create a new task")
async def create_task_endpoint(body: CreateTaskRequest) -> dict[str, Any]:
    try:
        return await create_task(**body.model_dump())
    except Exception as exc:
        logger.error(f"[/tasks POST] {exc}")
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/", summary="List tasks for a user")
async def list_tasks(
    user_id: str = Query(..., description="User ID"),
    status: Optional[str] = Query(None, description="Filter by status"),
    priority: Optional[str] = Query(None, description="Filter by priority"),
    limit: int = Query(50, le=200),
) -> list[dict[str, Any]]:
    try:
        return await get_tasks(user_id=user_id, status=status, priority=priority, limit=limit)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/overdue", summary="Get overdue tasks for a user")
async def list_overdue_tasks(
    user_id: str = Query(..., description="User ID"),
) -> list[dict[str, Any]]:
    try:
        return await get_overdue_tasks(user_id=user_id)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.patch("/{task_id}", summary="Update a task")
async def update_task_endpoint(
    task_id: str,
    body: UpdateTaskRequest,
) -> dict[str, Any]:
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update.")
    try:
        return await update_task(task_id=task_id, updates=updates)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.delete("/{task_id}", summary="Delete a task")
async def delete_task_endpoint(task_id: str) -> dict[str, Any]:
    try:
        return await delete_task(task_id=task_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.post("/{task_id}/score", summary="Re-compute priority score for a task")
async def score_task(task_id: str) -> dict[str, Any]:
    try:
        return await score_and_update_priority(task_id=task_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
