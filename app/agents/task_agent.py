"""
Task Agent — manages task lifecycle, prioritisation, and NL queries
about tasks.  Uses LangChain tools backed by the task_tool module.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from loguru import logger

from app.config import get_settings
from app.tools import (
    create_task,
    get_tasks,
    update_task,
    delete_task,
    get_overdue_tasks,
    score_and_update_priority,
)


SYSTEM_PROMPT = """You are the Task Agent in a multi-agent AI productivity system.

Your responsibilities:
1. Create, update, and delete tasks as instructed.
2. Retrieve and filter tasks based on user queries.
3. Prioritise tasks using the scoring formula:
   priority_score = (urgency * 0.4) + (importance * 0.4) + (base_priority * 0.2)
4. Identify overdue tasks and flag them.
5. Answer natural language questions about tasks.

Always respond with structured JSON when returning task data.
Be concise but thorough in your explanations.
"""


class TaskAgent:
    """
    LangChain-powered task management agent.
    Exposes `run()` for single-turn NL interactions and direct
    async helpers for programmatic use by the orchestrator.
    """

    def __init__(self) -> None:
        settings = get_settings()
        self.llm = ChatGoogleGenerativeAI(
            model=settings.gemini_model,
            google_api_key=settings.google_api_key,
            temperature=0,
        )

    async def run(self, user_id: str, query: str) -> str:
        """
        Process a natural-language task query and return a string response.
        The LLM decides which tool to invoke based on the query.
        """
        # Fetch current tasks to give the LLM context
        tasks = await get_tasks(user_id, limit=20)
        overdue = await get_overdue_tasks(user_id)

        context = (
            f"Current tasks ({len(tasks)} total, {len(overdue)} overdue):\n"
            + "\n".join(
                f"- [{t.get('status')}] {t.get('title')} "
                f"(priority: {t.get('priority')}, deadline: {t.get('deadline')})"
                for t in tasks[:10]
            )
        )

        messages = [
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=f"User context:\n{context}\n\nUser query: {query}"),
        ]

        response = await self.llm.ainvoke(messages)
        answer: str = response.content
        logger.info(f"[TaskAgent] Processed query for user {user_id}: {query[:60]}…")
        return answer

    async def get_today_tasks(self, user_id: str) -> list[dict[str, Any]]:
        """Return tasks due today, sorted by priority score."""
        tasks = await get_tasks(user_id, limit=100)
        today = datetime.utcnow().date()
        today_tasks = [
            t for t in tasks
            if t.get("deadline") and
            datetime.fromisoformat(t["deadline"]).date() == today
        ]
        return sorted(today_tasks, key=lambda x: x.get("priority_score", 0), reverse=True)

    async def get_delayed_tasks(self, user_id: str) -> list[dict[str, Any]]:
        """Return overdue / delayed tasks."""
        return await get_overdue_tasks(user_id)

    async def prioritise_all(self, user_id: str) -> list[dict[str, Any]]:
        """Re-score all non-done tasks for a user."""
        tasks = await get_tasks(user_id, limit=200)
        results = []
        for t in tasks:
            if t.get("status") != "done":
                try:
                    updated = await score_and_update_priority(t["_id"])
                    results.append(updated)
                except Exception as exc:
                    logger.warning(f"[TaskAgent] Could not score task {t['_id']}: {exc}")
        return results

    async def create(self, user_id: str, **kwargs: Any) -> dict[str, Any]:
        """Programmatic task creation proxy."""
        return await create_task(user_id=user_id, **kwargs)

    async def update(self, task_id: str, updates: dict[str, Any]) -> dict[str, Any]:
        """Programmatic task update proxy."""
        return await update_task(task_id, updates)
