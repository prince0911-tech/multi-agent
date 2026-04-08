"""
APScheduler background jobs for proactive AI features.
Jobs run on a configurable interval and alert users about
upcoming deadlines, overdue tasks, and risk conditions.
"""
from __future__ import annotations

from datetime import datetime

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from loguru import logger

from app.config import get_settings
from app.database.connection import get_db
from app.tools import get_overdue_tasks, score_and_update_priority, get_tasks


_scheduler: AsyncIOScheduler | None = None


async def _check_deadlines_job() -> None:
    """
    Scan all users for upcoming deadlines and overdue tasks.
    Persists alert records to MongoDB (alerts collection).
    """
    db = get_db()
    settings = get_settings()

    # Fetch all user IDs
    user_cursor = db.users.find({}, {"_id": 1})
    users = await user_cursor.to_list(length=500)

    now = datetime.utcnow()
    alerts_created = 0

    for user in users:
        user_id: str = str(user["_id"])

        overdue = await get_overdue_tasks(user_id)
        for task in overdue:
            # Avoid duplicate alerts within the same hour
            existing = await db.alerts.find_one({
                "user_id": user_id,
                "task_id": task["_id"],
                "type": "overdue",
                "created_at": {"$gte": datetime(now.year, now.month, now.day, now.hour)},
            })
            if not existing:
                await db.alerts.insert_one({
                    "user_id": user_id,
                    "task_id": task["_id"],
                    "type": "overdue",
                    "message": f"Task '{task.get('title')}' is overdue.",
                    "created_at": now,
                    "read": False,
                })
                alerts_created += 1

    if alerts_created:
        logger.info(f"[Scheduler] Deadline check created {alerts_created} alert(s).")


async def _reprioritise_tasks_job() -> None:
    """
    Re-score priority for all non-done tasks across all users.
    Runs less frequently to keep scores fresh.
    """
    db = get_db()
    cursor = db.tasks.find(
        {"status": {"$nin": ["done"]}},
        {"_id": 1},
    )
    task_docs = await cursor.to_list(length=1000)
    updated = 0
    for doc in task_docs:
        try:
            await score_and_update_priority(str(doc["_id"]))
            updated += 1
        except Exception as exc:
            logger.warning(f"[Scheduler] Failed to score task {doc['_id']}: {exc}")
    if updated:
        logger.info(f"[Scheduler] Re-prioritised {updated} task(s).")


async def _risk_detection_job() -> None:
    """
    Run risk analysis for all users and persist warnings.
    Imports RiskAgent locally to avoid circular imports at module load.
    """
    from app.agents.risk_agent import RiskAgent  # local import

    db = get_db()
    user_cursor = db.users.find({}, {"_id": 1})
    users = await user_cursor.to_list(length=500)

    agent = RiskAgent()
    for user in users:
        user_id = str(user["_id"])
        try:
            report = await agent.analyse(user_id)
            level = report.get("risk_level", "low")
            if level in ("high", "critical"):
                logger.warning(
                    f"[Scheduler] {level.upper()} risk for user {user_id}: "
                    f"{report.get('warnings', [])}"
                )
        except Exception as exc:
            logger.warning(f"[Scheduler] Risk job failed for user {user_id}: {exc}")


def get_scheduler() -> AsyncIOScheduler:
    """Return the global scheduler instance."""
    if _scheduler is None:
        raise RuntimeError("Scheduler not initialised. Call start_scheduler() first.")
    return _scheduler


def start_scheduler() -> AsyncIOScheduler:
    """
    Initialise and start the APScheduler with all background jobs.
    Should be called once during application startup.
    """
    global _scheduler
    settings = get_settings()

    _scheduler = AsyncIOScheduler(timezone=settings.scheduler_timezone)

    # Deadline / alert check — every N minutes
    _scheduler.add_job(
        _check_deadlines_job,
        trigger=IntervalTrigger(minutes=settings.deadline_check_interval_minutes),
        id="deadline_check",
        name="Deadline & Overdue Alert Check",
        replace_existing=True,
    )

    # Re-prioritisation — every hour
    _scheduler.add_job(
        _reprioritise_tasks_job,
        trigger=IntervalTrigger(hours=1),
        id="reprioritise",
        name="Task Re-prioritisation",
        replace_existing=True,
    )

    # Risk detection — every 2 hours
    _scheduler.add_job(
        _risk_detection_job,
        trigger=IntervalTrigger(hours=2),
        id="risk_detection",
        name="Risk Detection",
        replace_existing=True,
    )

    _scheduler.start()
    logger.info(
        f"[Scheduler] APScheduler started with {len(_scheduler.get_jobs())} job(s)."
    )
    return _scheduler


def stop_scheduler() -> None:
    """Gracefully shut down the scheduler."""
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("[Scheduler] APScheduler stopped.")
    _scheduler = None
