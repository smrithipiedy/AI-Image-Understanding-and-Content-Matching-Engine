"""Cost tracking model for AI calls."""

import uuid
from datetime import datetime
from sqlalchemy import String, DateTime, func, ForeignKey, Index, Numeric, Integer
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID
from app.core.database import Base


class Cost(Base):
    """Cost tracking for AI operations."""

    __tablename__ = "costs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False
    )
    operation: Mapped[str] = mapped_column(String(100), nullable=False)  # 'vision_classification', 'embedding_generation'
    model: Mapped[str] = mapped_column(String(100), nullable=False)  # 'bakllava:7b', 'nomic-embed-text'
    related_type: Mapped[str | None] = mapped_column(String(50), nullable=True)  # 'image', 'post', 'job'
    related_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    tokens_input: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tokens_output: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cost_usd: Mapped[float] = mapped_column(Numeric(10, 6), default=0.0, nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="success", nullable=False)  # 'success', 'failed'
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )

    __table_args__ = (
        Index("idx_costs_tenant", "tenant_id"),
        Index("idx_costs_related", "related_type", "related_id"),
        Index("idx_costs_operation", "operation"),
    )