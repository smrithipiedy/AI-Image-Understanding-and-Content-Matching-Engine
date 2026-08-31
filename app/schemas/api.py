"""API request and response Pydantic schemas."""

import uuid
from typing import List, Optional, Literal
from pydantic import BaseModel, Field, HttpUrl, field_validator


class ImageIngestRequest(BaseModel):
    """Payload for POST /api/v1/images/ingest."""
    urls: List[HttpUrl] = Field(..., min_length=1, max_length=50)


class JobResponse(BaseModel):
    """Response schema for background job operations."""
    id: uuid.UUID
    tenant_id: uuid.UUID
    type: str
    status: str
    progress: int
    payload: dict
    error: Optional[str] = None
    created_at: str


class ImageMetadataResponse(BaseModel):
    """Image metadata details schema."""
    subject: str
    category: str
    attributes: List[str]
    caption: str
    confidence: float
    vision_model: str
    is_low_confidence: bool


class ImageResponse(BaseModel):
    """Detailed image representation schema."""
    id: uuid.UUID
    tenant_id: uuid.UUID
    url: str
    filename: str
    sha256: str
    source_provider: str
    source_url: str
    license: str
    expected_category: Optional[str] = None
    status: str
    img_metadata: Optional[ImageMetadataResponse] = None
    created_at: str


class ImageListResponse(BaseModel):
    """Paginated list of images."""
    items: List[ImageResponse]
    total: int
    limit: int
    offset: int


class PostCreateRequest(BaseModel):
    """Request payload to create a new blog post."""
    title: str = Field(..., min_length=1, max_length=500)
    content: str = Field(..., min_length=1)
    expected_category: Optional[str] = None
    is_evaluation: bool = False


class ApprovalRequest(BaseModel):
    """Payload for reviewing/approving a match suggestion."""
    decision: Literal["approved", "rejected"]
    reviewer_note: Optional[str] = None


class CostRecordResponse(BaseModel):
    """Single cost log entry schema."""
    id: uuid.UUID
    tenant_id: uuid.UUID
    operation: str
    model: str
    related_type: Optional[str] = None
    related_id: Optional[uuid.UUID] = None
    tokens_input: Optional[int] = None
    tokens_output: Optional[int] = None
    cost_usd: float
    status: str
    created_at: str


class CostListResponse(BaseModel):
    """Paginated cost record summary schema."""
    items: List[CostRecordResponse]
    total: int
    total_cost_usd: float
    limit: int
    offset: int
