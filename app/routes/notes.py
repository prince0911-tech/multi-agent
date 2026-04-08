"""
/notes endpoints — note management.
"""
from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from loguru import logger

from app.tools import create_note, get_notes, update_note, delete_note, search_notes


router = APIRouter(prefix="/notes", tags=["Notes"])


class CreateNoteRequest(BaseModel):
    user_id: str
    title: str
    content: str
    tags: list[str] = []
    related_task_id: Optional[str] = None

    model_config = {
        "json_schema_extra": {
            "examples": [{
                "user_id": "user_abc123",
                "title": "Project kickoff ideas",
                "content": "Use agile methodology, weekly sprints...",
                "tags": ["project", "ideas"],
            }]
        }
    }


class UpdateNoteRequest(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    tags: Optional[list[str]] = None
    related_task_id: Optional[str] = None


@router.post("/", summary="Create a note")
async def create_note_endpoint(body: CreateNoteRequest) -> dict[str, Any]:
    try:
        return await create_note(**body.model_dump())
    except Exception as exc:
        logger.error(f"[/notes POST] {exc}")
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/", summary="List notes for a user")
async def list_notes(
    user_id: str = Query(...),
    tag: Optional[str] = Query(None),
    related_task_id: Optional[str] = Query(None),
    limit: int = Query(50, le=200),
) -> list[dict[str, Any]]:
    try:
        return await get_notes(
            user_id=user_id,
            tag=tag,
            related_task_id=related_task_id,
            limit=limit,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/search", summary="Search notes by keyword")
async def search_notes_endpoint(
    user_id: str = Query(...),
    keyword: str = Query(..., min_length=2),
) -> list[dict[str, Any]]:
    try:
        return await search_notes(user_id=user_id, keyword=keyword)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.patch("/{note_id}", summary="Update a note")
async def update_note_endpoint(
    note_id: str, body: UpdateNoteRequest
) -> dict[str, Any]:
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update.")
    try:
        return await update_note(note_id=note_id, updates=updates)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.delete("/{note_id}", summary="Delete a note")
async def delete_note_endpoint(note_id: str) -> dict[str, Any]:
    try:
        return await delete_note(note_id=note_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
