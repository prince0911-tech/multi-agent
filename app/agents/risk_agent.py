"""
Risk Agent — detects overload conditions, missed deadlines, and generates
structured risk warnings that are persisted to MongoDB.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from loguru import logger

from app.config import get_settings
from app.database.connection import get_db
from app.database.models import RiskWarning, RiskLevel
from app.tools import get_tasks, get_overdue_tasks


SYSTEM_PROMPT = """You are the Risk Agent in a multi-agent AI productivity system.

Your responsibilities:
1. Analyse task loads and deadlines to detect risk conditions.
2. Generate clear, actionable risk warnings.
3. Identify overloaded users (too many tasks due soon).
4. Flag missed deadlines and suggest remediation.
5. Escalate critical risks to the orchestrator.

Respond with structured JSON containing:
{
  "risk_level": "low|medium|high|critical",
  "warnings": ["warning1", "warning2"],
  "recommendations": ["action1", "action2"]
}
"""


class RiskAgent:
    """
    Risk detection agent that proactively monitors users' task loads.
    """

    def __init__(self) -> None:
        settings = get_settings()
        self.settings = settings
        self.llm = ChatOpenAI(
            model=settings.openai_model,
            api_key=settings.openai_api_key,
            temperature=0,
        )

    async def analyse(self, user_id: str) -> dict[str, Any]:
        """
        Perform a full risk analysis for a user.
        Returns a risk report and persists warnings to MongoDB.
        """
        tasks = await get_tasks(user_id, limit=200)
        overdue = await get_overdue_tasks(user_id)
        now = datetime.utcnow()

        # Tasks due within 24 hours
        urgent = [
            t for t in tasks
            if t.get("deadline") and
            0 < (datetime.fromisoformat(t["deadline"]) - now).total_seconds() / 3600 <= 24
            and t.get("status") not in ("done",)
        ]

        # Build summary for LLM
        summary = (
            f"Total active tasks: {len(tasks)}\n"
            f"Overdue tasks: {len(overdue)}\n"
            f"Due in next 24 h: {len(urgent)}\n"
            f"Overload threshold: {self.settings.overload_task_threshold}\n\n"
            "Overdue task titles:\n"
            + "\n".join(f"  - {t.get('title')}" for t in overdue[:10])
            + "\n\nUrgent task titles:\n"
            + "\n".join(f"  - {t.get('title')}" for t in urgent[:10])
        )

        messages = [
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=f"User risk analysis request:\n{summary}"),
        ]
        response = await self.llm.ainvoke(messages)

        # Try to parse structured JSON from LLM
        import json, re
        raw = response.content
        try:
            # Extract JSON block if wrapped in markdown
            match = re.search(r"\{.*\}", raw, re.DOTALL)
            report = json.loads(match.group(0)) if match else {"raw": raw}
        except Exception:
            report = {"raw": raw}

        # Persist warnings
        warnings = report.get("warnings", [])
        if warnings:
            await self._persist_warnings(
                user_id=user_id,
                level=report.get("risk_level", "medium"),
                warnings=warnings,
                related_task_ids=[t["_id"] for t in overdue[:20]],
            )

        logger.info(
            f"[RiskAgent] Risk analysis for user {user_id}: "
            f"level={report.get('risk_level', 'unknown')}, "
            f"warnings={len(warnings)}"
        )
        return report

    async def get_active_warnings(self, user_id: str) -> list[dict[str, Any]]:
        """Return unacknowledged risk warnings for a user."""
        db = get_db()
        cursor = db.risk_warnings.find(
            {"user_id": user_id, "acknowledged": False}
        ).sort("created_at", -1).limit(20)
        docs = await cursor.to_list(length=20)
        for d in docs:
            d["_id"] = str(d["_id"])
            if isinstance(d.get("created_at"), datetime):
                d["created_at"] = d["created_at"].isoformat()
        return docs

    async def acknowledge_warning(self, warning_id: str) -> dict[str, Any]:
        """Mark a risk warning as acknowledged."""
        db = get_db()
        result = await db.risk_warnings.find_one_and_update(
            {"_id": warning_id},
            {"$set": {"acknowledged": True}},
            return_document=True,
        )
        return {"acknowledged": warning_id} if result else {"error": "not found"}

    async def _persist_warnings(
        self,
        user_id: str,
        level: str,
        warnings: list[str],
        related_task_ids: list[str],
    ) -> None:
        """Store risk warnings in MongoDB."""
        db = get_db()
        try:
            risk_level = RiskLevel(level)
        except ValueError:
            risk_level = RiskLevel.MEDIUM

        for msg in warnings:
            warning = RiskWarning(
                user_id=user_id,
                level=risk_level,
                message=msg,
                related_task_ids=related_task_ids,
            )
            await db.risk_warnings.insert_one(
                warning.model_dump(by_alias=True)
            )
