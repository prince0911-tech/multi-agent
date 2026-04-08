"""
/events endpoints — calendar event management.
"""
from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from loguru import logger

from app.tools import create_event, get_events, delete_event, find_free_slots


router = APIRouter(prefix="/events", tags=["Events"])


class CreateEventRequest(BaseModel):
    user_id: str
    title: str
    start_time: str
    end_time: str
    description: str = ""
    participants: list[str] = []
    related_task_id: Optional[str] = None

    model_config = {
        "json_schema_extra": {
            "examples": [{
                "user_id": "user_abc123",
                "title": "Team standup",
                "start_time": "2024-07-10T09:00:00",
                "end_time": "2024-07-10T09:30:00",
                "participants": ["user_xyz456"],
            }]
        }
    }


@router.post("/", summary="Create a calendar event")
async def create_event_endpoint(body: CreateEventRequest) -> dict[str, Any]:
    try:
        return await create_event(**body.model_dump())
    except Exception as exc:
        logger.error(f"[/events POST] {exc}")
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/", summary="List events for a user")
async def list_events(
    user_id: str = Query(...),
    from_time: Optional[str] = Query(None, description="ISO datetime"),
    to_time: Optional[str] = Query(None, description="ISO datetime"),
    limit: int = Query(50, le=200),
) -> list[dict[str, Any]]:
    try:
        return await get_events(
            user_id=user_id,
            from_time=from_time,
            to_time=to_time,
            limit=limit,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/free-slots", summary="Find free time slots on a day")
async def free_slots(
    user_id: str = Query(...),
    date: str = Query(..., description="ISO date e.g. 2024-07-10"),
    duration_minutes: int = Query(60, description="Required slot length in minutes"),
) -> list[dict[str, str]]:
    try:
        return await find_free_slots(
            user_id=user_id,
            date=date,
            duration_minutes=duration_minutes,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.delete("/{event_id}", summary="Delete a calendar event")
async def delete_event_endpoint(event_id: str) -> dict[str, Any]:
    try:
        return await delete_event(event_id=event_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
