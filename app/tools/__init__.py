"""app/tools package — MCP-style tool wrappers"""
from app.tools.task_tool import (
    create_task, get_tasks, update_task, delete_task,
    get_overdue_tasks, score_and_update_priority,
)
from app.tools.calendar_tool import (
    create_event, get_events, delete_event,
    find_free_slots, get_shared_calendar,
)
from app.tools.notes_tool import (
    create_note, get_notes, update_note, delete_note, search_notes,
)

__all__ = [
    "create_task", "get_tasks", "update_task", "delete_task",
    "get_overdue_tasks", "score_and_update_priority",
    "create_event", "get_events", "delete_event",
    "find_free_slots", "get_shared_calendar",
    "create_note", "get_notes", "update_note", "delete_note", "search_notes",
]
