"""Blog Post model for content matching."""

import uuid
from datetime import datetime
from typing import Optional
from sqlalchemy import String, Text, Boolean, DateTime, ForeignKey, Index, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Post(Base):
    """Blog Post model."""

    __tablename__ = "posts"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"), nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    expected_category: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)  # 'red_fox', 'wolf', etc.
    embedding_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("embeddings.id"), nullable=True)
    expected_image_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("images.id"), nullable=True)
    is_evaluation: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    __table_args__ = (
        Index("idx_posts_tenant", "tenant_id"),
    )
