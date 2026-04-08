"""
Multi-Agent AI Productivity System — FastAPI application entry point.

Architecture:
  ┌──────────────────────────────────────────────────────┐
  │                    FastAPI App                       │
  │  /query  /tasks  /events  /notes  /insights  /users  │
  └──────────────────┬───────────────────────────────────┘
                     │
          ┌──────────▼──────────┐
          │  OrchestratorAgent  │  (LangGraph)
          └──┬──────┬──────┬───┘
             │      │      │
        ┌────▼─┐ ┌──▼──┐ ┌▼──────┐ ┌──────────┐
        │Task  │ │Cal. │ │Notes  │ │  Risk    │
        │Agent │ │Agent│ │Agent  │ │  Agent   │
        └──────┘ └─────┘ └───────┘ └──────────┘
             │      │        │           │
          ┌──▼──────▼────────▼───────────▼──┐
          │         MCP-style Tools          │
          │  task_tool / calendar_tool /     │
          │  notes_tool                      │
          └──────────────┬───────────────────┘
                         │
                  ┌──────▼──────┐
                  │   MongoDB   │
                  └─────────────┘
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from app.config import get_settings
from app.database import connect_db, close_db
from app.scheduler import start_scheduler, stop_scheduler
from app.routes import (
    query_router,
    tasks_router,
    events_router,
    notes_router,
    insights_router,
    users_router,
)


# ── Lifespan (startup / shutdown) ─────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application startup and shutdown lifecycle."""
    settings = get_settings()
    logger.info("🚀 Starting Multi-Agent AI Productivity System…")

    # Connect to MongoDB
    await connect_db()

    # Start background scheduler
    start_scheduler()

    logger.info(
        f"✅ Application ready | env={settings.app_env} | "
        f"model={settings.openai_model}"
    )
    yield

    # Shutdown
    logger.info("🛑 Shutting down…")
    stop_scheduler()
    await close_db()
    logger.info("Goodbye.")


# ── FastAPI app ────────────────────────────────────────────────────────────────

def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title="Multi-Agent AI Productivity System",
        description=(
            "A production-ready multi-agent AI system for task management, "
            "scheduling, and productivity insights. Powered by LangGraph, "
            "OpenAI, and MongoDB."
        ),
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    # CORS — origins configurable via CORS_ORIGINS env var
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Routers
    app.include_router(query_router)
    app.include_router(tasks_router)
    app.include_router(events_router)
    app.include_router(notes_router)
    app.include_router(insights_router)
    app.include_router(users_router)

    @app.get("/", tags=["Health"])
    async def root():
        """Health check and system info."""
        return {
            "status": "ok",
            "service": "Multi-Agent AI Productivity System",
            "version": "1.0.0",
            "docs": "/docs",
        }

    @app.get("/health", tags=["Health"])
    async def health():
        """Kubernetes / Cloud Run liveness probe."""
        return {"status": "healthy"}

    return app


app = create_app()
