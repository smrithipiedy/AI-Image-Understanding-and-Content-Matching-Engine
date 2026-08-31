"""Suggestion and Approval models for match results and human review."""

import uuid
from datetime import datetime
from typing import List, Optional
from sqlalchemy import String, Text, Float, Integer, DateTime, ForeignKey, Index, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Suggestion(Base):
    """Match result suggestion connecting a post and an image."""

    __tablename__ = "suggestions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    post_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("posts.id", ondelete="CASCADE"), nullable=False)
    image_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("images.id", ondelete="CASCADE"), nullable=False)
    similarity: Mapped[float] = mapped_column(Float, nullable=False)
    guard_decision: Mapped[str] = mapped_column(String(50), nullable=False)  # 'accepted', 'rejected', 'no_confident_match'
    guard_reasons: Mapped[list[str]] = mapped_column(JSONB, default=list, nullable=False)
    guard_explanation: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    vision_confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    rank: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    __table_args__ = (
        Index("idx_suggestions_post", "post_id"),
        Index("idx_suggestions_decision", "guard_decision"),
    )


class Approval(Base):
    """Human review decision (approval/rejection) for a suggestion."""

    __tablename__ = "approvals"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    suggestion_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("suggestions.id", ondelete="CASCADE"), nullable=False)
    decision: Mapped[str] = mapped_column(String(20), nullable=False)  # 'approved', 'rejected'
    reviewer_note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    decided_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    __table_args__ = (
        Index("idx_approvals_suggestion", "suggestion_id"),
    )
