"""Image model and related models."""

import uuid
from datetime import datetime
from enum import Enum as PyEnum
from sqlalchemy import String, Text, DateTime, func, ForeignKey, Index, CheckConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
from app.core.database import Base


class ImageStatus(str, PyEnum):
    """Image processing status."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    FLAGGED = "flagged"  # Low confidence


class Image(Base):
    """Image model."""

    __tablename__ = "images"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False
    )
    url: Mapped[str] = mapped_column(Text, nullable=False)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    source_provider: Mapped[str] = mapped_column(String(100), nullable=False)  # 'unsplash', 'pexels'
    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    license: Mapped[str] = mapped_column(String(100), nullable=False)  # 'Unsplash License', 'Pexels License'
    expected_category: Mapped[str | None] = mapped_column(String(100), nullable=True)  # For eval: 'red_fox', 'wolf', etc.
    status: Mapped[str] = mapped_column(String(50), default=ImageStatus.PENDING, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False
    )

    # Relationships
    metadata: Mapped["ImageMetadata"] = relationship(
        "ImageMetadata",
        back_populates="image",
        uselist=False,
        cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("idx_images_tenant", "tenant_id"),
        Index("idx_images_status", "status"),
        Index("idx_images_sha256", "sha256", unique=True),
    )


class ImageMetadata(Base):
    """Structured vision output metadata for an image."""

    __tablename__ = "image_metadata"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    image_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("images.id", ondelete="CASCADE"),
        nullable=False,
        unique=True
    )
    subject: Mapped[str] = mapped_column(String(255), nullable=False)  # "red fox"
    category: Mapped[str] = mapped_column(String(100), nullable=False)  # "animal"
    attributes: Mapped[list] = mapped_column(
        default=list,
        nullable=False
    )  # ["orange fur", "wild", "forest"]
    caption: Mapped[str] = mapped_column(Text, nullable=False)  # "A red fox standing in a forest"
    confidence: Mapped[float] = mapped_column(nullable=False)  # 0.0 - 1.0
    vision_model: Mapped[str] = mapped_column(String(100), nullable=False)  # "bakllava:7b"
    is_low_confidence: Mapped[bool] = mapped_column(default=False, nullable=False)
    validated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )

    # Relationships
    image: Mapped["Image"] = relationship("Image", back_populates="metadata")

    __table_args__ = (
        Index("idx_image_metadata_image", "image_id"),
        Index("idx_image_metadata_subject", "subject"),
        Index("idx_image_metadata_category", "category"),
        CheckConstraint("confidence >= 0 AND confidence <= 1", name="ck_confidence_range"),
    )