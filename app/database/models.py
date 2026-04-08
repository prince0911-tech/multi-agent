"""
Pydantic v2 models for MongoDB documents.
ObjectId is handled as a plain string for JSON serialisation.
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Optional

from bson import ObjectId
from pydantic import BaseModel, Field, field_validator


# ─────────────────────────────────────────────────────────────────────────────
# Helper
# ─────────────────────────────────────────────────────────────────────────────

def new_id() -> str:
    return str(ObjectId())


# ─────────────────────────────────────────────────────────────────────────────
# Enums
# ─────────────────────────────────────────────────────────────────────────────

class TaskStatus(str, Enum):
    TODO = "todo"
    IN_PROGRESS = "in_progress"
    DONE = "done"
    OVERDUE = "overdue"


class TaskPriority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


# ─────────────────────────────────────────────────────────────────────────────
# User
# ─────────────────────────────────────────────────────────────────────────────

class UserPreferences(BaseModel):
    preferred_work_start: str = "09:00"   # HH:MM
    preferred_work_end: str = "17:00"
    timezone: str = "UTC"
    focus_duration_minutes: int = 90


class UserModel(BaseModel):
    id: str = Field(default_factory=new_id, alias="_id")
    name: str
    email: str
    preferences: UserPreferences = Field(default_factory=UserPreferences)
    created_at: datetime = Field(default_factory=datetime.utcnow)

    model_config = {"populate_by_name": True}


# ─────────────────────────────────────────────────────────────────────────────
# Task
# ─────────────────────────────────────────────────────────────────────────────

class TaskModel(BaseModel):
    id: str = Field(default_factory=new_id, alias="_id")
    user_id: str
    title: str
    description: str = ""
    status: TaskStatus = TaskStatus.TODO
    priority: TaskPriority = TaskPriority.MEDIUM
    importance: int = Field(default=5, ge=1, le=10)   # 1-10 scale
    deadline: Optional[datetime] = None
    assigned_to: Optional[str] = None       # user_id of assignee
    tags: list[str] = Field(default_factory=list)
    priority_score: float = 0.0             # computed by scoring agent
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    model_config = {"populate_by_name": True}


# ─────────────────────────────────────────────────────────────────────────────
# Calendar Event
# ─────────────────────────────────────────────────────────────────────────────

class EventModel(BaseModel):
    id: str = Field(default_factory=new_id, alias="_id")
    user_id: str
    title: str
    description: str = ""
    start_time: datetime
    end_time: datetime
    participants: list[str] = Field(default_factory=list)   # user_ids
    related_task_id: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

    model_config = {"populate_by_name": True}


# ─────────────────────────────────────────────────────────────────────────────
# Note
# ─────────────────────────────────────────────────────────────────────────────

class NoteModel(BaseModel):
    id: str = Field(default_factory=new_id, alias="_id")
    user_id: str
    title: str
    content: str
    tags: list[str] = Field(default_factory=list)
    related_task_id: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    model_config = {"populate_by_name": True}


# ─────────────────────────────────────────────────────────────────────────────
# Risk Warning
# ─────────────────────────────────────────────────────────────────────────────

class RiskWarning(BaseModel):
    id: str = Field(default_factory=new_id, alias="_id")
    user_id: str
    level: RiskLevel
    message: str
    related_task_ids: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    acknowledged: bool = False

    model_config = {"populate_by_name": True}


# ─────────────────────────────────────────────────────────────────────────────
# Agent message (inter-agent communication log)
# ─────────────────────────────────────────────────────────────────────────────

class AgentMessage(BaseModel):
    id: str = Field(default_factory=new_id, alias="_id")
    from_agent: str
    to_agent: str
    payload: dict[str, Any]
    created_at: datetime = Field(default_factory=datetime.utcnow)

    model_config = {"populate_by_name": True}
