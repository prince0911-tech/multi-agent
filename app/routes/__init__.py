"""app/routes package"""
from app.routes.query import router as query_router
from app.routes.tasks import router as tasks_router
from app.routes.events import router as events_router
from app.routes.notes import router as notes_router
from app.routes.insights import router as insights_router
from app.routes.users import router as users_router

__all__ = [
    "query_router",
    "tasks_router",
    "events_router",
    "notes_router",
    "insights_router",
    "users_router",
]
