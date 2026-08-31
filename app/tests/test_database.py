"""Tests for database layer - TDD: written BEFORE implementation."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import uuid
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession
from app.models import Tenant, Image, ImageMetadata, Job, Cost
from app.models.image import ImageStatus
from app.models.job import JobStatus, JobType
from app.db.repositories import (
    TenantRepository,
    ImageRepository,
    ImageMetadataRepository,
    JobRepository,
    CostRepository,
)


class TestTenantRepository:
    """Tests for TenantRepository."""

    @pytest.fixture
    def mock_session(self):
        return AsyncMock(spec=AsyncSession)

    @pytest.fixture
    def repo(self, mock_session):
        return TenantRepository(mock_session)

    @pytest.mark.asyncio
    async def test_get_by_name_found(self, repo, mock_session):
        """Should return tenant when found."""
        mock_tenant = MagicMock(spec=Tenant)
        mock_tenant.name = "demo-tenant"
        mock_session.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=mock_tenant)))

        result = await repo.get_by_name("demo-tenant")

        assert result == mock_tenant

    @pytest.mark.asyncio
    async def test_get_by_name_not_found(self, repo, mock_session):
        """Should return None when not found."""
        mock_session.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None)))

        result = await repo.get_by_name("nonexistent")

        assert result is None

    @pytest.mark.asyncio
    async def test_get_or_create_existing(self, repo, mock_session):
        """Should return existing tenant."""
        mock_tenant = MagicMock(spec=Tenant)
        mock_tenant.name = "demo-tenant"
        mock_session.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=mock_tenant)))

        result = await repo.get_or_create("demo-tenant")

        assert result == mock_tenant
        mock_session.add.assert_not_called()

    @pytest.mark.asyncio
    async def test_get_or_create_new(self, repo, mock_session):
        """Should create new tenant when not exists."""
        mock_session.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None)))
        mock_session.flush = AsyncMock()

        result = await repo.get_or_create("new-tenant")

        assert result.name == "new-tenant"
        mock_session.add.assert_called_once()
        mock_session.flush.assert_called_once()


class TestImageRepository:
    """Tests for ImageRepository."""

    @pytest.fixture
    def mock_session(self):
        return AsyncMock(spec=AsyncSession)

    @pytest.fixture
    def repo(self, mock_session):
        return ImageRepository(mock_session)

    @pytest.fixture
    def tenant_id(self):
        return uuid.uuid4()

    @pytest.fixture
    def image_id(self):
        return uuid.uuid4()

    @pytest.mark.asyncio
    async def test_create_image(self, repo, mock_session, tenant_id):
        """Should create and return image."""
        mock_session.flush = AsyncMock()

        image = await repo.create(
            tenant_id=tenant_id,
            url="https://example.com/img.jpg",
            filename="img.jpg",
            sha256="abc123",
            source_provider="unsplash",
            source_url="https://unsplash.com/photos/abc123",
            license="Unsplash License",
            expected_category="red_fox",
        )

        assert image.tenant_id == tenant_id
        assert image.url == "https://example.com/img.jpg"
        assert image.sha256 == "abc123"
        assert image.status == ImageStatus.PENDING
        mock_session.add.assert_called_once()
        mock_session.flush.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_by_sha256(self, repo, mock_session, tenant_id, image_id):
        """Should find image by SHA256."""
        mock_image = MagicMock(spec=Image)
        mock_image.sha256 = "abc123"
        mock_session.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=mock_image)))

        result = await repo.get_by_sha256("abc123", tenant_id)

        assert result == mock_image

    @pytest.mark.asyncio
    async def test_get_by_url(self, repo, mock_session, tenant_id, image_id):
        """Should find image by URL."""
        mock_image = MagicMock(spec=Image)
        mock_session.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=mock_image)))

        result = await repo.get_by_url("https://example.com/img.jpg", tenant_id)

        assert result == mock_image

    @pytest.mark.asyncio
    async def test_update_status(self, repo, mock_session, image_id):
        """Should update image status."""
        mock_session.execute = AsyncMock()

        await repo.update_status(image_id, ImageStatus.COMPLETED)

        mock_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_list_images(self, repo, mock_session, tenant_id):
        """Should return paginated images with total count."""
        mock_images = [MagicMock(spec=Image) for _ in range(3)]
        mock_count_result = MagicMock()
        mock_count_result.scalar = MagicMock(return_value=3)
        mock_list_result = MagicMock()
        mock_list_result.scalars.return_value.all.return_value = mock_images
        mock_session.execute = AsyncMock(side_effect=[mock_count_result, mock_list_result])

        images, total = await repo.list_images(tenant_id, limit=10, offset=0)

        assert images == mock_images
        assert total == 3


class TestImageMetadataRepository:
    """Tests for ImageMetadataRepository."""

    @pytest.fixture
    def mock_session(self):
        return AsyncMock(spec=AsyncSession)

    @pytest.fixture
    def repo(self, mock_session):
        return ImageMetadataRepository(mock_session)

    @pytest.fixture
    def image_id(self):
        return uuid.uuid4()

    @pytest.mark.asyncio
    async def test_create_metadata(self, repo, mock_session, image_id):
        """Should create metadata with validated vision output."""
        mock_session.flush = AsyncMock()

        metadata = await repo.create(
            image_id=image_id,
            subject="red fox",
            category="animal",
            attributes=["orange fur", "wild"],
            caption="A red fox in forest",
            confidence=0.94,
            vision_model="bakllava:7b",
            is_low_confidence=False,
        )

        assert metadata.image_id == image_id
        assert metadata.subject == "red fox"
        assert metadata.confidence == 0.94
        assert metadata.is_low_confidence is False
        assert metadata.validated_at is not None
        mock_session.add.assert_called_once()
        mock_session.flush.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_metadata_low_confidence(self, repo, mock_session, image_id):
        """Should flag low confidence metadata."""
        mock_session.flush = AsyncMock()

        metadata = await repo.create(
            image_id=image_id,
            subject="gray wolf",
            category="animal",
            attributes=["gray fur"],
            caption="A wolf",
            confidence=0.45,
            vision_model="bakllava:7b",
            is_low_confidence=True,
        )

        assert metadata.is_low_confidence is True
        assert metadata.confidence == 0.45


class TestJobRepository:
    """Tests for JobRepository."""

    @pytest.fixture
    def mock_session(self):
        return AsyncMock(spec=AsyncSession)

    @pytest.fixture
    def repo(self, mock_session):
        return JobRepository(mock_session)

    @pytest.fixture
    def tenant_id(self):
        return uuid.uuid4()

    @pytest.mark.asyncio
    async def test_create_job(self, repo, mock_session, tenant_id):
        """Should create job with pending status."""
        mock_session.flush = AsyncMock()

        job = await repo.create(
            tenant_id=tenant_id,
            job_type=JobType.IMAGE_INGESTION,
            payload={"urls": ["https://example.com/img.jpg"]},
            idempotency_key="test-key",
        )

        assert job.tenant_id == tenant_id
        assert job.type == JobType.IMAGE_INGESTION
        assert job.status == JobStatus.PENDING
        assert job.idempotency_key == "test-key"
        mock_session.add.assert_called_once()
        mock_session.flush.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_by_idempotency_key(self, repo, mock_session):
        """Should find job by idempotency key."""
        mock_job = MagicMock(spec=Job)
        mock_job.idempotency_key = "test-key"
        mock_session.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=mock_job)))

        result = await repo.get_by_idempotency_key("test-key")

        assert result == mock_job

    @pytest.mark.asyncio
    async def test_update_status_processing(self, repo, mock_session):
        """Should update status and set started_at."""
        job_id = uuid.uuid4()
        mock_session.execute = AsyncMock()

        await repo.update_status(job_id, JobStatus.PROCESSING, progress=50)

        mock_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_status_completed(self, repo, mock_session):
        """Should update status and set completed_at."""
        job_id = uuid.uuid4()
        mock_session.execute = AsyncMock()

        await repo.update_status(job_id, JobStatus.COMPLETED, progress=100)

        mock_session.execute.assert_called_once()


class TestCostRepository:
    """Tests for CostRepository."""

    @pytest.fixture
    def mock_session(self):
        return AsyncMock(spec=AsyncSession)

    @pytest.fixture
    def repo(self, mock_session):
        return CostRepository(mock_session)

    @pytest.fixture
    def tenant_id(self):
        return uuid.uuid4()

    @pytest.mark.asyncio
    async def test_create_cost(self, repo, mock_session, tenant_id):
        """Should create cost record."""
        related_id = uuid.uuid4()
        mock_session.flush = AsyncMock()

        cost = await repo.create(
            tenant_id=tenant_id,
            operation="vision_classification",
            model="bakllava:7b",
            related_type="image",
            related_id=related_id,
            tokens_input=100,
            tokens_output=50,
            cost_usd=0.0,
            status="success",
        )

        assert cost.tenant_id == tenant_id
        assert cost.operation == "vision_classification"
        assert cost.cost_usd == 0.0
        mock_session.add.assert_called_once()
        mock_session.flush.assert_called_once()

    @pytest.mark.asyncio
    async def test_list_costs_with_totals(self, repo, mock_session, tenant_id):
        """Should return costs with total count and sum."""
        from decimal import Decimal
        mock_costs = [MagicMock(spec=Cost) for _ in range(2)]
        mock_count_result = MagicMock()
        mock_count_result.scalar = MagicMock(return_value=5)
        mock_sum_result = MagicMock()
        mock_sum_result.scalar = MagicMock(return_value=Decimal("0.00"))
        mock_list_result = MagicMock()
        mock_list_result.scalars.return_value.all.return_value = mock_costs
        mock_session.execute = AsyncMock(side_effect=[mock_count_result, mock_sum_result, mock_list_result])

        costs, total, total_cost = await repo.list_costs(tenant_id, limit=10, offset=0)

        assert costs == mock_costs
        assert total == 5
        assert total_cost == 0.0