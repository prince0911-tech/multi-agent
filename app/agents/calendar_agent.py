"""
Calendar Agent — reads calendar events, finds free slots, and
auto-schedules tasks.  Communicates results back to the orchestrator
so that Task Agent can create preparation tasks.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from loguru import logger

from app.config import get_settings
from app.tools import (
    create_event,
    get_events,
    find_free_slots,
    get_shared_calendar,
)


SYSTEM_PROMPT = """You are the Calendar Agent in a multi-agent AI productivity system.

Your responsibilities:
1. Read and summarise calendar events for a user.
2. Find free time slots on requested days.
3. Auto-schedule tasks into available free slots.
4. Support multi-user shared calendar views.
5. Suggest preparation time blocks before important events.

When auto-scheduling, always:
- Respect user work hours (09:00-17:00 by default).
- Prefer slots that do not fragment focus time.
- Return structured event data.
"""


class CalendarAgent:
    """
    Calendar management agent with auto-scheduling capability.
    """

    def __init__(self) -> None:
        settings = get_settings()
        self.llm = ChatOpenAI(
            model=settings.openai_model,
            api_key=settings.openai_api_key,
            temperature=0,
        )

    async def run(self, user_id: str, query: str) -> str:
        """Process a natural-language calendar query."""
        today = datetime.utcnow().date().isoformat()
        events = await get_events(
            user_id=user_id,
            from_time=f"{today}T00:00:00",
            to_time=f"{today}T23:59:59",
        )

        context = (
            f"Today's events ({len(events)}):\n"
            + "\n".join(
                f"- {e.get('title')} from {e.get('start_time')} to {e.get('end_time')}"
                for e in events
            )
        )

        messages = [
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=f"Context:\n{context}\n\nQuery: {query}"),
        ]
        response = await self.llm.ainvoke(messages)
        logger.info(f"[CalendarAgent] Processed query for user {user_id}")
        return response.content

    async def auto_schedule_task(
        self,
        user_id: str,
        task_title: str,
        duration_minutes: int = 60,
        preferred_date: str | None = None,
    ) -> dict[str, Any] | None:
        """
        Find the next available free slot and create a calendar event.
        Returns the created event or None if no slot is found.
        """
        settings = get_settings()
        date = preferred_date or datetime.utcnow().date().isoformat()

        # Try up to 7 days ahead
        for day_offset in range(7):
            check_date = (
                datetime.fromisoformat(date) + timedelta(days=day_offset)
            ).date().isoformat()

            slots = await find_free_slots(
                user_id=user_id,
                date=check_date,
                duration_minutes=duration_minutes,
            )
            if slots:
                slot = slots[0]
                # Create event for the first available slot
                event = await create_event(
                    user_id=user_id,
                    title=f"[Auto] {task_title}",
                    start_time=slot["start"],
                    end_time=slot["end"],
                    description=f"Auto-scheduled by Calendar Agent for task: {task_title}",
                )
                logger.info(
                    f"[CalendarAgent] Auto-scheduled '{task_title}' on {check_date} "
                    f"for user {user_id}"
                )
                return event

        logger.warning(
            f"[CalendarAgent] Could not find free slot for '{task_title}' "
            f"within 7 days for user {user_id}"
        )
        return None

    async def get_today_events(self, user_id: str) -> list[dict[str, Any]]:
        today = datetime.utcnow().date().isoformat()
        return await get_events(
            user_id=user_id,
            from_time=f"{today}T00:00:00",
            to_time=f"{today}T23:59:59",
        )

    async def get_free_slots_today(
        self, user_id: str, duration_minutes: int = 60
    ) -> list[dict[str, str]]:
        today = datetime.utcnow().date().isoformat()
        return await find_free_slots(
            user_id=user_id,
            date=today,
            duration_minutes=duration_minutes,
        )

    async def get_shared_view(
        self, user_ids: list[str], date: str
    ) -> list[dict[str, Any]]:
        """Return a merged calendar view for collaboration."""
        return await get_shared_calendar(user_ids=user_ids, date=date)
