"""
/insights endpoints — productivity dashboard and analytics.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from loguru import logger

from app.database.connection import get_db


router = APIRouter(prefix="/insights", tags=["Insights"])


@router.get("/", summary="Productivity insights for a user")
async def get_insights(
    user_id: str = Query(..., description="User ID"),
    days: int = Query(30, ge=1, le=365, description="Lookback window in days"),
) -> dict[str, Any]:
    """
    Return productivity statistics:
    - Tasks completed in the period
    - Overdue / pending tasks
    - Completion rate
    - Daily productivity pattern (tasks completed per day)
    - Risk warnings summary
    """
    db = get_db()
    since = datetime.utcnow() - timedelta(days=days)

    # ── Aggregate task stats ──────────────────────────────────────────────
    total = await db.tasks.count_documents({"user_id": user_id})
    completed = await db.tasks.count_documents(
        {"user_id": user_id, "status": "done", "updated_at": {"$gte": since}}
    )
    total_in_period = await db.tasks.count_documents(
        {"user_id": user_id, "created_at": {"$gte": since}}
    )
    overdue = await db.tasks.count_documents({
        "user_id": user_id,
        "deadline": {"$lt": datetime.utcnow()},
        "status": {"$nin": ["done"]},
    })
    in_progress = await db.tasks.count_documents(
        {"user_id": user_id, "status": "in_progress"}
    )

    # Completion rate: tasks completed vs tasks created in the same period
    completion_rate = round(completed / total_in_period * 100, 1) if total_in_period > 0 else 0.0

    # ── Daily completion pattern ──────────────────────────────────────────
    pipeline = [
        {
            "$match": {
                "user_id": user_id,
                "status": "done",
                "updated_at": {"$gte": since},
            }
        },
        {
            "$group": {
                "_id": {
                    "$dateToString": {"format": "%Y-%m-%d", "date": "$updated_at"}
                },
                "count": {"$sum": 1},
            }
        },
        {"$sort": {"_id": 1}},
    ]
    daily_cursor = db.tasks.aggregate(pipeline)
    daily_data = await daily_cursor.to_list(length=365)
    daily_pattern = {d["_id"]: d["count"] for d in daily_data}

    # ── Priority distribution ─────────────────────────────────────────────
    priority_pipeline = [
        {"$match": {"user_id": user_id, "status": {"$nin": ["done"]}}},
        {"$group": {"_id": "$priority", "count": {"$sum": 1}}},
    ]
    prio_cursor = db.tasks.aggregate(priority_pipeline)
    prio_docs = await prio_cursor.to_list(length=10)
    priority_dist = {d["_id"]: d["count"] for d in prio_docs}

    # ── Risk warnings ─────────────────────────────────────────────────────
    active_warnings = await db.risk_warnings.count_documents(
        {"user_id": user_id, "acknowledged": False}
    )

    # ── Alerts (scheduled) ────────────────────────────────────────────────
    unread_alerts = await db.alerts.count_documents(
        {"user_id": user_id, "read": False}
    )

    return {
        "user_id": user_id,
        "period_days": days,
        "task_stats": {
            "total": total,
            "completed_in_period": completed,
            "overdue": overdue,
            "in_progress": in_progress,
            "total_created_in_period": total_in_period,
            "completion_rate_percent": completion_rate,
        },
        "priority_distribution": priority_dist,
        "daily_completions": daily_pattern,
        "active_risk_warnings": active_warnings,
        "unread_alerts": unread_alerts,
        "generated_at": datetime.utcnow().isoformat(),
    }


@router.get("/users", summary="Multi-user productivity comparison")
async def multi_user_insights(
    user_ids: str = Query(..., description="Comma-separated user IDs"),
    days: int = Query(7, ge=1, le=90),
) -> dict[str, Any]:
    """
    Compare productivity metrics across multiple users.
    Useful for team leads / managers.
    """
    db = get_db()
    since = datetime.utcnow() - timedelta(days=days)
    id_list = [uid.strip() for uid in user_ids.split(",")]

    results = {}
    for uid in id_list:
        completed = await db.tasks.count_documents(
            {"user_id": uid, "status": "done", "updated_at": {"$gte": since}}
        )
        overdue = await db.tasks.count_documents({
            "user_id": uid,
            "deadline": {"$lt": datetime.utcnow()},
            "status": {"$nin": ["done"]},
        })
        results[uid] = {"completed": completed, "overdue": overdue}

    return {"period_days": days, "users": results}


@router.get("/alerts", summary="Get unread alerts for a user")
async def get_alerts(
    user_id: str = Query(...),
    limit: int = Query(20, le=100),
) -> list[dict[str, Any]]:
    """Return unread scheduler alerts for a user."""
    db = get_db()
    cursor = db.alerts.find(
        {"user_id": user_id, "read": False}
    ).sort("created_at", -1).limit(limit)
    docs = await cursor.to_list(length=limit)
    for d in docs:
        d["_id"] = str(d["_id"])
        if isinstance(d.get("created_at"), datetime):
            d["created_at"] = d["created_at"].isoformat()
    return docs


@router.patch("/alerts/{alert_id}/read", summary="Mark an alert as read")
async def mark_alert_read(alert_id: str) -> dict[str, Any]:
    db = get_db()
    result = await db.alerts.find_one_and_update(
        {"_id": alert_id},
        {"$set": {"read": True}},
        return_document=True,
    )
    if result is None:
        raise HTTPException(status_code=404, detail="Alert not found.")
    return {"marked_read": alert_id}
