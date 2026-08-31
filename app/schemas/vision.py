"""Pydantic schemas for vision model output validation."""

from pydantic import BaseModel, Field, field_validator
from typing import Optional
from datetime import datetime
import uuid


class VisionOutput(BaseModel):
    """Schema for validated vision model output.

    This is the core schema that enforces structured output from the vision model.
    Every vision response MUST pass through this validation before entering trusted state.
    """

    subject: str = Field(..., min_length=1, max_length=255, description="Primary subject of the image")
    category: str = Field(..., min_length=1, max_length=100, description="High-level category")
    attributes: list[str] = Field(default_factory=list, description="List of visual attributes")
    caption: str = Field(..., min_length=1, description="Natural language description")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Model confidence score 0-1")

    @field_validator("subject", "category", "caption")
    @classmethod
    def not_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Field cannot be empty or whitespace")
        return v.strip()

    @field_validator("attributes")
    @classmethod
    def validate_attributes(cls, v: list[str]) -> list[str]:
        if not isinstance(v, list):
            raise ValueError("Attributes must be a list")
        return [attr.strip() for attr in v if attr and attr.strip()]


class ImageMetadataResponse(BaseModel):
    """Response schema for image metadata."""

    subject: str
    category: str
    attributes: list[str]
    caption: str
    confidence: float
    is_low_confidence: bool
    vision_model: str
    validated_at: Optional[datetime] = None


class ImageResponse(BaseModel):
    """Response schema for image with metadata."""

    id: uuid.UUID
    url: str
    filename: str
    status: str
    metadata: Optional[ImageMetadataResponse] = None


class ImageListResponse(BaseModel):
    """Response schema for paginated image list."""

    images: list[ImageResponse]
    total: int
    limit: int
    offset: int


class ImageIngestRequest(BaseModel):
    """Request schema for image ingestion."""

    urls: list[str] = Field(..., min_length=1, max_length=50)

    @field_validator("urls")
    @classmethod
    def validate_urls(cls, v: list[str]) -> list[str]:
        for url in v:
            if not url.startswith(("http://", "https://")):
                raise ValueError(f"Invalid URL: {url}")
        return v


class JobResponse(BaseModel):
    """Response schema for job status."""

    id: uuid.UUID
    type: str
    status: str
    progress: int
    payload: dict
    error: Optional[str] = None
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class CostResponse(BaseModel):
    """Response schema for cost records."""

    id: uuid.UUID
    operation: str
    model: str
    related_type: Optional[str] = None
    related_id: Optional[uuid.UUID] = None
    tokens_input: Optional[int] = None
    tokens_output: Optional[int] = None
    cost_usd: float
    status: str
    created_at: datetime


class CostListResponse(BaseModel):
    """Response schema for paginated cost list."""

    costs: list[CostResponse]
    total: int
    total_cost_usd: float