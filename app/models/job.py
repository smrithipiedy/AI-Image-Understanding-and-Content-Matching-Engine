"""Job model for background batch processing."""

import uuid
from datetime import datetime
from enum import Enum as PyEnum
from sqlalchemy import String, Text, DateTime, func, ForeignKey, Index, JSON
from sqlalchemy.orm import Mapped, mapped_column
from typing import Any
from sqlalchemy.dialects.postgresql import UUID, JSONB
from app.core.database import Base


class JobStatus(str, PyEnum):
    """Job processing status."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class JobType(str, PyEnum):
    """Job types."""
    IMAGE_INGESTION = "image_ingestion"
    EMBEDDING_GENERATION = "embedding_generation"


class Job(Base):
    """Background job model."""

    __tablename__ = "jobs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False
    )
    type: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(50), default=JobStatus.PENDING, nullable=False)
    progress: Mapped[int] = mapped_column(default=0, nullable=False)  # 0-100
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    idempotency_key: Mapped[str | None] = mapped_column(String(255), unique=True, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("idx_jobs_tenant", "tenant_id"),
        Index("idx_jobs_status", "status"),
        Index("idx_jobs_idempotency", "idempotency_key"),
    )