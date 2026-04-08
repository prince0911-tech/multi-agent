"""
/users endpoints — user management and preference personalisation.
"""
from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from loguru import logger

from app.database.connection import get_db
from app.database.models import UserModel, UserPreferences


router = APIRouter(prefix="/users", tags=["Users"])


class CreateUserRequest(BaseModel):
    name: str
    email: str
    preferences: Optional[dict] = None

    model_config = {
        "json_schema_extra": {
            "examples": [{
                "name": "Alice Smith",
                "email": "alice@example.com",
                "preferences": {
                    "preferred_work_start": "08:00",
                    "preferred_work_end": "16:00",
                    "timezone": "America/New_York",
                },
            }]
        }
    }


class UpdatePreferencesRequest(BaseModel):
    preferred_work_start: Optional[str] = None
    preferred_work_end: Optional[str] = None
    timezone: Optional[str] = None
    focus_duration_minutes: Optional[int] = None


def _serialize_user(doc: dict) -> dict:
    if "_id" in doc:
        doc["_id"] = str(doc["_id"])
    from datetime import datetime
    if isinstance(doc.get("created_at"), datetime):
        doc["created_at"] = doc["created_at"].isoformat()
    return doc


@router.post("/", summary="Create a user")
async def create_user(body: CreateUserRequest) -> dict[str, Any]:
    db = get_db()
    existing = await db.users.find_one({"email": body.email})
    if existing:
        raise HTTPException(status_code=409, detail="Email already registered.")

    prefs = UserPreferences(**(body.preferences or {}))
    user = UserModel(name=body.name, email=body.email, preferences=prefs)
    doc = user.model_dump(by_alias=True)
    await db.users.insert_one(doc)
    logger.info(f"[/users] Created user {user.id} ({body.email})")
    return _serialize_user(doc)


@router.get("/{user_id}", summary="Get user by ID")
async def get_user(user_id: str) -> dict[str, Any]:
    db = get_db()
    doc = await db.users.find_one({"_id": user_id})
    if not doc:
        raise HTTPException(status_code=404, detail="User not found.")
    return _serialize_user(doc)


@router.patch("/{user_id}/preferences", summary="Update user preferences")
async def update_preferences(
    user_id: str, body: UpdatePreferencesRequest
) -> dict[str, Any]:
    db = get_db()
    updates = {
        f"preferences.{k}": v
        for k, v in body.model_dump().items()
        if v is not None
    }
    if not updates:
        raise HTTPException(status_code=400, detail="No preferences to update.")

    result = await db.users.find_one_and_update(
        {"_id": user_id},
        {"$set": updates},
        return_document=True,
    )
    if result is None:
        raise HTTPException(status_code=404, detail="User not found.")
    logger.info(f"[/users] Updated preferences for {user_id}: {list(updates.keys())}")
    return _serialize_user(result)


@router.get("/", summary="List all users")
async def list_users(limit: int = Query(50, le=200)) -> list[dict[str, Any]]:
    db = get_db()
    cursor = db.users.find({}).limit(limit)
    docs = await cursor.to_list(length=limit)
    return [_serialize_user(d) for d in docs]
