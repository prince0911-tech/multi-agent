"""
Application configuration using pydantic-settings.
All values are read from environment variables or a .env file.
"""
from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # OpenAI
    openai_api_key: str = "sk-placeholder"
    openai_model: str = "gpt-4o"

    # MongoDB
    mongodb_uri: str = "mongodb://localhost:27017"
    mongodb_db_name: str = "multi_agent_db"

    # Application
    app_env: str = "development"
    app_host: str = "0.0.0.0"
    app_port: int = 8080
    secret_key: str = "change-me-in-production"

    # Scheduler
    scheduler_timezone: str = "UTC"
    deadline_check_interval_minutes: int = 30

    # Vector memory
    faiss_index_path: str = "./data/faiss_index"
    embedding_model: str = "all-MiniLM-L6-v2"

    # Risk thresholds
    overdue_warning_hours: int = 24
    overload_task_threshold: int = 10


@lru_cache
def get_settings() -> Settings:
    """Return a cached singleton Settings instance."""
    return Settings()
