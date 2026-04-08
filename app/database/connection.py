"""
MongoDB async connection using Motor.
Provides a shared AsyncIOMotorClient and convenience helpers.
"""
import motor.motor_asyncio
from loguru import logger
from app.config import get_settings


_client: motor.motor_asyncio.AsyncIOMotorClient | None = None


def get_client() -> motor.motor_asyncio.AsyncIOMotorClient:
    """Return the shared Motor client (must call connect_db first)."""
    if _client is None:
        raise RuntimeError("Database not initialised. Call connect_db() first.")
    return _client


def get_db() -> motor.motor_asyncio.AsyncIOMotorDatabase:
    """Return the application database."""
    settings = get_settings()
    return get_client()[settings.mongodb_db_name]


async def connect_db() -> None:
    """Create Motor client and verify connectivity."""
    global _client
    settings = get_settings()
    logger.info(f"Connecting to MongoDB at {settings.mongodb_uri} …")
    _client = motor.motor_asyncio.AsyncIOMotorClient(settings.mongodb_uri)
    # Ping to confirm connection
    await _client.admin.command("ping")
    logger.info("MongoDB connection established.")

    # Ensure indexes for frequently queried fields
    db = get_db()
    await db.tasks.create_index("user_id")
    await db.tasks.create_index("deadline")
    await db.tasks.create_index("status")
    await db.events.create_index("user_id")
    await db.events.create_index("start_time")
    await db.notes.create_index("user_id")
    await db.users.create_index("email", unique=True)
    logger.info("MongoDB indexes ensured.")


async def close_db() -> None:
    """Close the Motor client cleanly."""
    global _client
    if _client:
        _client.close()
        _client = None
        logger.info("MongoDB connection closed.")
