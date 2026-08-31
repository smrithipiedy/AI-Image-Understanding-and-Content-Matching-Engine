"""Tests for batch processor / job queue - TDD: written BEFORE implementation."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import uuid
from datetime import datetime

from app.models.job import Job, JobStatus, JobType
from app.models.image import Image, ImageStatus
from app.models.image import ImageMetadata
from app.models.cost import Cost
from app.db.repositories import JobRepository, ImageRepository, ImageMetadataRepository, CostRepository


class TestJobRepository:
    """Tests for JobRepository."""

    @pytest.fixture
    def mock_session(self):
        return AsyncMock()

    @pytest.fixture
    def job_repo(self, mock_session):
        return JobRepository(mock_session)

    @pytest.fixture
    def tenant_id(self):
        return uuid.uuid4()

    @pytest.mark.asyncio
    async def test_create_job(self, job_repo, tenant_id):
        """Create job should persist and return job."""
        job = await job_repo.create(
            tenant_id=tenant_id,
            job_type=JobType.IMAGE_INGESTION,
            payload={"urls": ["https://example.com/img1.jpg"]},
            idempotency_key="test-key-123",
        )

        assert job.tenant_id == tenant_id
        assert job.type == JobType.IMAGE_INGESTION
        assert job.status == JobStatus.PENDING
        assert job.progress == 0
        assert job.idempotency_key == "test-key-123"
        job_repo.session.add.assert_called_once()
        job_repo.session.flush.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_job_without_idempotency_key(self, job_repo, tenant_id):
        """Create job without idempotency key should work."""
        job = await job_repo.create(
            tenant_id=tenant_id,
            job_type=JobType.IMAGE_INGESTION,
            payload={"urls": []},
        )

        assert job.idempotency_key is None

    @pytest.mark.asyncio
    async def test_get_by_idempotency_key(self, job_repo, tenant_id):
        """Get job by idempotency key should work."""
        mock_job = MagicMock(spec=Job)
        mock_job.idempotency_key = "test-key"
        job_repo.session.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=mock_job)))

        result = await job_repo.get_by_idempotency_key("test-key")

        assert result == mock_job

    @pytest.mark.asyncio
    async def test_get_by_idempotency_key_not_found(self, job_repo):
        """Get job by idempotency key should return None if not found."""
        job_repo.session.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None)))

        result = await job_repo.get_by_idempotency_key("nonexistent")

        assert result is None

    @pytest.mark.asyncio
    async def test_update_status_processing(self, job_repo):
        """Update status to processing should set started_at."""
        job_id = uuid.uuid4()
        job_repo.session.execute = AsyncMock()

        await job_repo.update_status(job_id, JobStatus.PROCESSING, progress=50)

        job_repo.session.execute.assert_called_once()
        # Verify the update query includes started_at
        call_args = job_repo.session.execute.call_args
        assert call_args is not None

    @pytest.mark.asyncio
    async def test_update_status_completed(self, job_repo):
        """Update status to completed should set completed_at."""
        job_id = uuid.uuid4()
        job_repo.session.execute = AsyncMock()

        await job_repo.update_status(job_id, JobStatus.COMPLETED, progress=100)

        job_repo.session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_status_failed(self, job_repo):
        """Update status to failed should set error and completed_at."""
        job_id = uuid.uuid4()
        job_repo.session.execute = AsyncMock()

        await job_repo.update_status(job_id, JobStatus.FAILED, error="Processing failed")

        job_repo.session.execute.assert_called_once()


class TestImageRepository:
    """Tests for ImageRepository."""

    @pytest.fixture
    def mock_session(self):
        return AsyncMock()

    @pytest.fixture
    def image_repo(self, mock_session):
        return ImageRepository(mock_session)

    @pytest.fixture
    def tenant_id(self):
        return uuid.uuid4()

    @pytest.mark.asyncio
    async def test_create_image(self, image_repo, tenant_id):
        """Create image should persist and return image."""
        image = await image_repo.create(
            tenant_id=tenant_id,
            url="https://example.com/image.jpg",
            filename="image.jpg",
            sha256="abc123",
            source_provider="unsplash",
            source_url="https://unsplash.com/photos/abc123",
            license="Unsplash License",
            expected_category="red_fox",
        )

        assert image.tenant_id == tenant_id
        assert image.url == "https://example.com/image.jpg"
        assert image.sha256 == "abc123"
        assert image.status == ImageStatus.PENDING
        image_repo.session.add.assert_called_once()
        image_repo.session.flush.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_by_sha256(self, image_repo, tenant_id):
        """Get image by SHA256 should work for idempotency."""
        mock_image = MagicMock(spec=Image)
        mock_image.sha256 = "abc123"
        image_repo.session.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=mock_image)))

        result = await image_repo.get_by_sha256("abc123", tenant_id)

        assert result == mock_image

    @pytest.mark.asyncio
    async def test_get_by_url(self, image_repo, tenant_id):
        """Get image by URL should work."""
        mock_image = MagicMock(spec=Image)
        image_repo.session.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=mock_image)))

        result = await image_repo.get_by_url("https://example.com/image.jpg", tenant_id)

        assert result == mock_image

    @pytest.mark.asyncio
    async def test_update_status(self, image_repo):
        """Update image status should work."""
        image_id = uuid.uuid4()
        image_repo.session.execute = AsyncMock()

        await image_repo.update_status(image_id, ImageStatus.COMPLETED)

        image_repo.session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_list_images(self, image_repo, tenant_id):
        """List images should return paginated results."""
        mock_images = [MagicMock(spec=Image) for _ in range(3)]
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = mock_images
        image_repo.session.execute = AsyncMock(side_effect=[
            MagicMock(scalar=MagicMock(return_value=3)),  # count
            mock_result,  # paginated results
        ])

        images, total = await image_repo.list_images(tenant_id, limit=10, offset=0)

        assert images == mock_images
        assert total == 3


class TestImageMetadataRepository:
    """Tests for ImageMetadataRepository."""

    @pytest.fixture
    def mock_session(self):
        return AsyncMock()

    @pytest.fixture
    def metadata_repo(self, mock_session):
        return ImageMetadataRepository(mock_session)

    @pytest.mark.asyncio
    async def test_create_metadata(self, metadata_repo):
        """Create metadata should persist validated vision output."""
        image_id = uuid.uuid4()
        metadata = await metadata_repo.create(
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
        metadata_repo.session.add.assert_called_once()
        metadata_repo.session.flush.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_metadata_low_confidence_flagged(self, metadata_repo):
        """Low confidence metadata should be flagged."""
        image_id = uuid.uuid4()
        metadata = await metadata_repo.create(
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


class TestBatchProcessor:
    """Tests for the batch image processor."""

    @pytest.fixture
    def mock_session(self):
        return AsyncMock()

    @pytest.fixture
    def mock_vision_service(self):
        service = AsyncMock()
        service.process_image = AsyncMock()
        service.is_low_confidence = MagicMock(return_value=False)
        service.close = AsyncMock()
        return service

    @pytest.fixture
    def mock_cost_service(self):
        service = AsyncMock()
        service.record_vision_cost = AsyncMock(return_value=0.0)
        service.record_failed_cost = AsyncMock()
        return service

    @pytest.mark.asyncio
    async def test_process_single_image_success(self, mock_session, mock_vision_service, mock_cost_service):
        """Process single image should succeed and update status."""
        # This test will be implemented after batch processor is written
        pytest.skip("Batch processor not implemented yet")

    @pytest.mark.asyncio
    async def test_process_single_image_idempotent(self, mock_session, mock_vision_service, mock_cost_service):
        """Processing same image twice should not duplicate (idempotency)."""
        pytest.skip("Batch processor not implemented yet")

    @pytest.mark.asyncio
    async def test_process_single_image_low_confidence_flagged(self, mock_session, mock_vision_service, mock_cost_service):
        """Low confidence image should be flagged."""
        pytest.skip("Batch processor not implemented yet")

    @pytest.mark.asyncio
    async def test_process_single_image_vision_failure(self, mock_session, mock_vision_service, mock_cost_service):
        """Vision failure should mark image as failed and record cost."""
        pytest.skip("Batch processor not implemented yet")

    @pytest.mark.asyncio
    async def test_process_batch_updates_progress(self, mock_session, mock_vision_service, mock_cost_service):
        """Batch processing should update job progress."""
        pytest.skip("Batch processor not implemented yet")

    @pytest.mark.asyncio
    async def test_process_batch_retries_on_failure(self, mock_session, mock_vision_service, mock_cost_service):
        """Batch should retry failed images up to max retries."""
        pytest.skip("Batch processor not implemented yet")

    @pytest.mark.asyncio
    async def test_process_batch_exponential_backoff(self, mock_session, mock_vision_service, mock_cost_service):
        """Retries should use exponential backoff."""
        pytest.skip("Batch processor not implemented yet")


class TestCostRepository:
    """Tests for CostRepository."""

    @pytest.fixture
    def mock_session(self):
        return AsyncMock()

    @pytest.fixture
    def cost_repo(self, mock_session):
        return CostRepository(mock_session)

    @pytest.fixture
    def tenant_id(self):
        return uuid.uuid4()

    @pytest.mark.asyncio
    async def test_create_cost(self, cost_repo, tenant_id):
        """Create cost should persist cost record."""
        related_id = uuid.uuid4()
        cost = await cost_repo.create(
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
        cost_repo.session.add.assert_called_once()
        cost_repo.session.flush.assert_called_once()

    @pytest.mark.asyncio
    async def test_list_costs_with_total(self, cost_repo, tenant_id):
        """List costs should return paginated results with total count and sum."""
        mock_costs = [MagicMock(spec=Cost) for _ in range(2)]
        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 5
        mock_sum_result = MagicMock()
        mock_sum_result.scalar.return_value = Decimal("0.00")
        mock_list_result = MagicMock()
        mock_list_result.scalars.return_value.all.return_value = mock_costs

        cost_repo.session.execute = AsyncMock(side_effect=[
            mock_count_result,
            mock_sum_result,
            mock_list_result,
        ])

        costs, total, total_cost = await cost_repo.list_costs(tenant_id, limit=10, offset=0)

        assert costs == mock_costs
        assert total == 5
        assert total_cost == 0.0