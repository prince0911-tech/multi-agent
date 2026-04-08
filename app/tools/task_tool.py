"""
Task Tool — MCP-style wrapper for task CRUD operations.
All methods return plain dicts so they can be serialised as tool outputs.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from bson import ObjectId
from loguru import logger

from app.database.connection import get_db
from app.database.models import TaskModel, TaskStatus, TaskPriority


def _serialize(doc: dict) -> dict:
    """Convert MongoDB document to JSON-serialisable dict."""
    if doc and "_id" in doc:
        doc["_id"] = str(doc["_id"])
    for key in ("deadline", "created_at", "updated_at"):
        if key in doc and isinstance(doc[key], datetime):
            doc[key] = doc[key].isoformat()
    return doc


async def create_task(
    user_id: str,
    title: str,
    description: str = "",
    priority: str = "medium",
    importance: int = 5,
    deadline: Optional[str] = None,
    assigned_to: Optional[str] = None,
    tags: Optional[list[str]] = None,
) -> dict[str, Any]:
    """
    Create a new task in MongoDB.
    Returns the created task document.
    """
    db = get_db()
    task = TaskModel(
        user_id=user_id,
        title=title,
        description=description,
        priority=TaskPriority(priority),
        importance=importance,
        deadline=datetime.fromisoformat(deadline) if deadline else None,
        assigned_to=assigned_to,
        tags=tags or [],
    )
    doc = task.model_dump(by_alias=True)
    await db.tasks.insert_one(doc)
    logger.info(f"[TaskTool] Created task '{title}' for user {user_id}")
    return _serialize(doc)


async def get_tasks(
    user_id: str,
    status: Optional[str] = None,
    priority: Optional[str] = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """
    Retrieve tasks for a user, with optional filters.
    """
    db = get_db()
    query: dict[str, Any] = {"user_id": user_id}
    if status:
        query["status"] = status
    if priority:
        query["priority"] = priority

    cursor = db.tasks.find(query).sort("priority_score", -1).limit(limit)
    docs = await cursor.to_list(length=limit)
    return [_serialize(d) for d in docs]


async def update_task(task_id: str, updates: dict[str, Any]) -> dict[str, Any]:
    """
    Update fields on an existing task.
    Returns the updated document.
    """
    db = get_db()
    updates["updated_at"] = datetime.utcnow()
    result = await db.tasks.find_one_and_update(
        {"_id": task_id},
        {"$set": updates},
        return_document=True,
    )
    if result is None:
        raise ValueError(f"Task {task_id} not found.")
    logger.info(f"[TaskTool] Updated task {task_id}: {list(updates.keys())}")
    return _serialize(result)


async def delete_task(task_id: str) -> dict[str, Any]:
    """Delete a task by ID."""
    db = get_db()
    result = await db.tasks.find_one_and_delete({"_id": task_id})
    if result is None:
        raise ValueError(f"Task {task_id} not found.")
    logger.info(f"[TaskTool] Deleted task {task_id}")
    return {"deleted": task_id}


async def get_overdue_tasks(user_id: str) -> list[dict[str, Any]]:
    """Return all tasks past their deadline that are not yet done."""
    db = get_db()
    now = datetime.utcnow()
    cursor = db.tasks.find({
        "user_id": user_id,
        "deadline": {"$lt": now},
        "status": {"$nin": [TaskStatus.DONE.value]},
    })
    docs = await cursor.to_list(length=100)
    return [_serialize(d) for d in docs]


async def score_and_update_priority(task_id: str) -> dict[str, Any]:
    """
    Compute a priority score:
        score = urgency_factor * 0.4 + importance * 0.4 + (status_factor) * 0.2
    and persist it on the task document.
    """
    db = get_db()
    doc = await db.tasks.find_one({"_id": task_id})
    if not doc:
        raise ValueError(f"Task {task_id} not found.")

    now = datetime.utcnow()
    importance = doc.get("importance", 5)
    deadline: Optional[datetime] = doc.get("deadline")

    # Urgency: higher score the closer the deadline
    if deadline:
        hours_remaining = (deadline - now).total_seconds() / 3600
        if hours_remaining <= 0:
            urgency = 10.0
        elif hours_remaining <= 24:
            urgency = 9.0
        elif hours_remaining <= 72:
            urgency = 7.0
        elif hours_remaining <= 168:
            urgency = 5.0
        else:
            urgency = 3.0
    else:
        urgency = 2.0

    priority_map = {"low": 1, "medium": 3, "high": 7, "critical": 10}
    base_priority = priority_map.get(doc.get("priority", "medium"), 3)

    score = (urgency * 0.4) + (importance * 0.4) + (base_priority * 0.2)
    return await update_task(task_id, {"priority_score": round(score, 2)})
