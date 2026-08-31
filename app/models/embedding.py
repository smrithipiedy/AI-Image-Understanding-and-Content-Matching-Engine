"""Embedding model for vector representation of images and posts."""

import uuid
from datetime import datetime
from typing import List, Optional
from sqlalchemy import String, DateTime, ForeignKey, Index, func
from sqlalchemy.dialects.postgresql import JSONB, ARRAY, FLOAT
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Embedding(Base):
    """Vector embedding model for image captions and post contents."""

    __tablename__ = "embeddings"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"), nullable=False)
    source_type: Mapped[str] = mapped_column(String(50), nullable=False)  # 'image_caption', 'post_text'
    source_id: Mapped[uuid.UUID] = mapped_column(nullable=False)          # references images.id or posts.id
    vector: Mapped[list[float]] = mapped_column(JSONB, nullable=False)    # 768-dim float list
    model: Mapped[str] = mapped_column(String(100), nullable=False)       # 'nomic-embed-text'
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    __table_args__ = (
        Index("idx_embeddings_tenant", "tenant_id"),
        Index("idx_embeddings_source", "source_type", "source_id"),
    )
