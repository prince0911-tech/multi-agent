"""
Calendar Tool — MCP-style wrapper for event CRUD and free-slot detection.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Optional

from loguru import logger

from app.database.connection import get_db
from app.database.models import EventModel


def _serialize(doc: dict) -> dict:
    if doc and "_id" in doc:
        doc["_id"] = str(doc["_id"])
    for key in ("start_time", "end_time", "created_at"):
        if key in doc and isinstance(doc[key], datetime):
            doc[key] = doc[key].isoformat()
    return doc


async def create_event(
    user_id: str,
    title: str,
    start_time: str,
    end_time: str,
    description: str = "",
    participants: Optional[list[str]] = None,
    related_task_id: Optional[str] = None,
) -> dict[str, Any]:
    """Create a calendar event."""
    db = get_db()
    event = EventModel(
        user_id=user_id,
        title=title,
        description=description,
        start_time=datetime.fromisoformat(start_time),
        end_time=datetime.fromisoformat(end_time),
        participants=participants or [],
        related_task_id=related_task_id,
    )
    doc = event.model_dump(by_alias=True)
    await db.events.insert_one(doc)
    logger.info(f"[CalendarTool] Created event '{title}' for user {user_id}")
    return _serialize(doc)


async def get_events(
    user_id: str,
    from_time: Optional[str] = None,
    to_time: Optional[str] = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """Retrieve events for a user within a time range."""
    db = get_db()
    query: dict[str, Any] = {"user_id": user_id}
    if from_time or to_time:
        time_filter: dict[str, Any] = {}
        if from_time:
            time_filter["$gte"] = datetime.fromisoformat(from_time)
        if to_time:
            time_filter["$lte"] = datetime.fromisoformat(to_time)
        query["start_time"] = time_filter

    cursor = db.events.find(query).sort("start_time", 1).limit(limit)
    docs = await cursor.to_list(length=limit)
    return [_serialize(d) for d in docs]


async def delete_event(event_id: str) -> dict[str, Any]:
    """Delete an event by ID."""
    db = get_db()
    result = await db.events.find_one_and_delete({"_id": event_id})
    if result is None:
        raise ValueError(f"Event {event_id} not found.")
    return {"deleted": event_id}


async def find_free_slots(
    user_id: str,
    date: str,          # ISO date string e.g. "2024-07-10"
    duration_minutes: int = 60,
    work_start: str = "09:00",
    work_end: str = "17:00",
) -> list[dict[str, str]]:
    """
    Find free time slots on a given day for a user.
    Returns a list of {start, end} dicts for available slots.
    """
    db = get_db()
    day = datetime.fromisoformat(date)
    tz_offset = timedelta(0)  # UTC

    work_start_dt = day.replace(
        hour=int(work_start.split(":")[0]),
        minute=int(work_start.split(":")[1]),
        second=0,
        microsecond=0,
    )
    work_end_dt = day.replace(
        hour=int(work_end.split(":")[0]),
        minute=int(work_end.split(":")[1]),
        second=0,
        microsecond=0,
    )

    # Fetch all events on that day
    events = await get_events(
        user_id=user_id,
        from_time=work_start_dt.isoformat(),
        to_time=work_end_dt.isoformat(),
    )

    # Build busy intervals
    busy: list[tuple[datetime, datetime]] = []
    for ev in events:
        busy.append((
            datetime.fromisoformat(ev["start_time"]),
            datetime.fromisoformat(ev["end_time"]),
        ))
    busy.sort(key=lambda x: x[0])

    # Find gaps
    free_slots: list[dict[str, str]] = []
    cursor_time = work_start_dt

    for start, end in busy:
        if cursor_time < start:
            gap_minutes = (start - cursor_time).total_seconds() / 60
            if gap_minutes >= duration_minutes:
                free_slots.append({
                    "start": cursor_time.isoformat(),
                    "end": start.isoformat(),
                })
        cursor_time = max(cursor_time, end)

    # Check gap after last event
    if cursor_time < work_end_dt:
        gap_minutes = (work_end_dt - cursor_time).total_seconds() / 60
        if gap_minutes >= duration_minutes:
            free_slots.append({
                "start": cursor_time.isoformat(),
                "end": work_end_dt.isoformat(),
            })

    logger.info(
        f"[CalendarTool] Found {len(free_slots)} free slot(s) on {date} "
        f"for user {user_id}"
    )
    return free_slots


async def get_shared_calendar(user_ids: list[str], date: str) -> list[dict[str, Any]]:
    """
    Return merged events for multiple users on a given day.
    Useful for multi-user collaboration.
    """
    db = get_db()
    day = datetime.fromisoformat(date)
    day_end = day.replace(hour=23, minute=59, second=59)

    cursor = db.events.find({
        "user_id": {"$in": user_ids},
        "start_time": {"$gte": day, "$lte": day_end},
    }).sort("start_time", 1)

    docs = await cursor.to_list(length=200)
    return [_serialize(d) for d in docs]
