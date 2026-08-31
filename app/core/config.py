"""Application configuration using Pydantic Settings."""

from pydantic_settings import BaseSettings
from pydantic import Field
from typing import Optional


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Database
    database_url: str = Field(
        default="postgresql+asyncpg://postgres:postgres@localhost:5432/flyrank",
        alias="DATABASE_URL"
    )

    # Ollama
    ollama_base_url: str = Field(
        default="http://localhost:11434",
        alias="OLLAMA_BASE_URL"
    )
    vision_model: str = Field(
        default="bakllava:7b",
        alias="VISION_MODEL"
    )
    embedding_model: str = Field(
        default="nomic-embed-text",
        alias="EMBEDDING_MODEL"
    )

    # App
    app_host: str = Field(default="0.0.0.0", alias="APP_HOST")
    app_port: int = Field(default=8000, alias="APP_PORT")
    tenant_id: str = Field(default="demo-tenant", alias="TENANT_ID")

    # Budget Guard
    max_budget_usd: float = Field(default=0.00, alias="MAX_BUDGET_USD")

    # Thresholds (Phase 3)
    similarity_threshold: float = Field(default=0.75, alias="SIMILARITY_THRESHOLD")
    vision_confidence_threshold: float = Field(default=0.70, alias="VISION_CONFIDENCE_THRESHOLD")

    # Logging
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


settings = Settings()