"""
Notes Tool — MCP-style wrapper for note CRUD operations.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from loguru import logger

from app.database.connection import get_db
from app.database.models import NoteModel


def _serialize(doc: dict) -> dict:
    if doc and "_id" in doc:
        doc["_id"] = str(doc["_id"])
    for key in ("created_at", "updated_at"):
        if key in doc and isinstance(doc[key], datetime):
            doc[key] = doc[key].isoformat()
    return doc


async def create_note(
    user_id: str,
    title: str,
    content: str,
    tags: Optional[list[str]] = None,
    related_task_id: Optional[str] = None,
) -> dict[str, Any]:
    """Create a new note."""
    db = get_db()
    note = NoteModel(
        user_id=user_id,
        title=title,
        content=content,
        tags=tags or [],
        related_task_id=related_task_id,
    )
    doc = note.model_dump(by_alias=True)
    await db.notes.insert_one(doc)
    logger.info(f"[NotesTool] Created note '{title}' for user {user_id}")
    return _serialize(doc)


async def get_notes(
    user_id: str,
    tag: Optional[str] = None,
    related_task_id: Optional[str] = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """Retrieve notes for a user with optional tag/task filters."""
    db = get_db()
    query: dict[str, Any] = {"user_id": user_id}
    if tag:
        query["tags"] = tag
    if related_task_id:
        query["related_task_id"] = related_task_id

    cursor = db.notes.find(query).sort("updated_at", -1).limit(limit)
    docs = await cursor.to_list(length=limit)
    return [_serialize(d) for d in docs]


async def update_note(note_id: str, updates: dict[str, Any]) -> dict[str, Any]:
    """Update note fields."""
    db = get_db()
    updates["updated_at"] = datetime.utcnow()
    result = await db.notes.find_one_and_update(
        {"_id": note_id},
        {"$set": updates},
        return_document=True,
    )
    if result is None:
        raise ValueError(f"Note {note_id} not found.")
    logger.info(f"[NotesTool] Updated note {note_id}")
    return _serialize(result)


async def delete_note(note_id: str) -> dict[str, Any]:
    """Delete a note by ID."""
    db = get_db()
    result = await db.notes.find_one_and_delete({"_id": note_id})
    if result is None:
        raise ValueError(f"Note {note_id} not found.")
    return {"deleted": note_id}


async def search_notes(user_id: str, keyword: str) -> list[dict[str, Any]]:
    """Full-text search across note titles and content."""
    db = get_db()
    # MongoDB text search (requires text index; falls back to regex)
    try:
        cursor = db.notes.find(
            {"user_id": user_id, "$text": {"$search": keyword}},
            {"score": {"$meta": "textScore"}},
        ).sort([("score", {"$meta": "textScore"})]).limit(20)
        docs = await cursor.to_list(length=20)
    except Exception:
        # Fallback: case-insensitive regex search
        import re
        pattern = re.compile(keyword, re.IGNORECASE)
        cursor = db.notes.find({
            "user_id": user_id,
            "$or": [{"title": pattern}, {"content": pattern}],
        }).limit(20)
        docs = await cursor.to_list(length=20)

    return [_serialize(d) for d in docs]
