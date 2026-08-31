"""Pytest configuration and shared fixtures."""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock
import uuid
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession
from app.models import Tenant, Image, ImageMetadata, Job, Cost
from app.models.image import ImageStatus
from app.models.job import JobStatus, JobType


@pytest.fixture
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def mock_session():
    """Mock async database session."""
    return AsyncMock(spec=AsyncSession)


@pytest.fixture
def sample_tenant_id():
    """Sample tenant UUID."""
    return uuid.uuid4()


@pytest.fixture
def sample_image_id():
    """Sample image UUID."""
    return uuid.uuid4()


@pytest.fixture
def sample_job_id():
    """Sample job UUID."""
    return uuid.uuid4()


@pytest.fixture
def mock_tenant(sample_tenant_id):
    """Mock tenant object."""
    tenant = MagicMock(spec=Tenant)
    tenant.id = sample_tenant_id
    tenant.name = "demo-tenant"
    tenant.created_at = datetime.utcnow()
    return tenant


@pytest.fixture
def mock_image(sample_image_id, sample_tenant_id):
    """Mock image object."""
    image = MagicMock(spec=Image)
    image.id = sample_image_id
    image.tenant_id = sample_tenant_id
    image.url = "https://example.com/image.jpg"
    image.filename = "image.jpg"
    image.sha256 = "abc123"
    image.source_provider = "unsplash"
    image.source_url = "https://unsplash.com/photos/abc123"
    image.license = "Unsplash License"
    image.expected_category = "red_fox"
    image.status = ImageStatus.PENDING
    image.created_at = datetime.utcnow()
    image.updated_at = datetime.utcnow()
    return image


@pytest.fixture
def mock_image_metadata(sample_image_id):
    """Mock image metadata object."""
    metadata = MagicMock(spec=ImageMetadata)
    metadata.id = uuid.uuid4()
    metadata.image_id = sample_image_id
    metadata.subject = "red fox"
    metadata.category = "animal"
    metadata.attributes = ["orange fur", "wild", "forest"]
    metadata.caption = "A red fox standing in a forest"
    metadata.confidence = 0.94
    metadata.vision_model = "bakllava:7b"
    metadata.is_low_confidence = False
    metadata.validated_at = datetime.utcnow()
    metadata.created_at = datetime.utcnow()
    return metadata


@pytest.fixture
def mock_job(sample_job_id, sample_tenant_id):
    """Mock job object."""
    job = MagicMock(spec=Job)
    job.id = sample_job_id
    job.tenant_id = sample_tenant_id
    job.type = JobType.IMAGE_INGESTION
    job.status = JobStatus.PENDING
    job.progress = 0
    job.payload = {"urls": ["https://example.com/image.jpg"]}
    job.error = None
    job.idempotency_key = "test-key"
    job.created_at = datetime.utcnow()
    job.started_at = None
    job.completed_at = None
    return job


@pytest.fixture
def mock_cost():
    """Mock cost object."""
    cost = MagicMock(spec=Cost)
    cost.id = uuid.uuid4()
    cost.tenant_id = uuid.uuid4()
    cost.operation = "vision_classification"
    cost.model = "bakllava:7b"
    cost.related_type = "image"
    cost.related_id = uuid.uuid4()
    cost.tokens_input = 100
    cost.tokens_output = 50
    cost.cost_usd = 0.0
    cost.status = "success"
    cost.created_at = datetime.utcnow()
    return cost