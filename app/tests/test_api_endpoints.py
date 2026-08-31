"""Tests for API endpoints."""

import pytest
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient

from app.main import app
from app.core.database import get_db
from app.models import Tenant, Image, ImageMetadata, Job, Cost
from app.models.image import ImageStatus
from app.models.job import JobStatus, JobType


@pytest.fixture
def mock_db_session():
    """Create a mock database session."""
    session = AsyncMock()
    return session


@pytest.fixture
def client(mock_db_session):
    """FastAPI TestClient with overridden DB session dependency and mocked init_db."""
    app.dependency_overrides[get_db] = lambda: mock_db_session
    with patch("app.main.init_db", new_callable=AsyncMock):
        with TestClient(app) as test_client:
            yield test_client
    app.dependency_overrides.clear()


class TestImageIngestEndpoint:
    """Tests for POST /api/v1/images/ingest."""

    def test_ingest_valid_urls(self, client, mock_db_session):
        """Valid URLs should create a job and return 202."""
        mock_job = MagicMock(spec=Job)
        mock_job.id = uuid.uuid4()
        mock_job.status = "pending"

        with patch("app.api.v1.images.JobRepository") as MockJobRepo, \
             patch("app.api.v1.images.BatchProcessor") as MockBatchProc, \
             patch("app.api.v1.images.TenantRepository") as MockTenantRepo:

            tenant_instance = AsyncMock()
            tenant_instance.get_or_create.return_value = MagicMock(id=uuid.uuid4())
            MockTenantRepo.return_value = tenant_instance

            job_instance = AsyncMock()
            job_instance.create.return_value = mock_job
            MockJobRepo.return_value = job_instance

            proc_instance = AsyncMock()
            proc_instance.process_job = AsyncMock()
            MockBatchProc.return_value = proc_instance

            payload = {"urls": ["https://images.unsplash.com/photo-1517849845537-4d257902454a"]}
            response = client.post("/api/v1/images/ingest", json=payload)

            assert response.status_code == 202
            assert "job_id" in response.json()
            assert response.json()["status"] == "pending"

    def test_ingest_empty_urls_rejected(self, client):
        """Empty URLs list should return 422."""
        response = client.post("/api/v1/images/ingest", json={"urls": []})
        assert response.status_code == 422

    def test_ingest_invalid_url_rejected(self, client):
        """Invalid URL format should return 422."""
        response = client.post("/api/v1/images/ingest", json={"urls": ["not_a_valid_url"]})
        assert response.status_code == 422

    def test_ingest_too_many_urls_rejected(self, client):
        """More than 50 URLs should return 422."""
        urls = [f"https://example.com/img{i}.jpg" for i in range(51)]
        response = client.post("/api/v1/images/ingest", json={"urls": urls})
        assert response.status_code == 422

    def test_ingest_returns_job_id(self, client, mock_db_session):
        """Response should contain job_id and status."""
        job_id = uuid.uuid4()
        mock_job = MagicMock(spec=Job)
        mock_job.id = job_id
        mock_job.status = "pending"

        with patch("app.api.v1.images.JobRepository") as MockJobRepo, \
             patch("app.api.v1.images.BatchProcessor") as MockBatchProc, \
             patch("app.api.v1.images.TenantRepository") as MockTenantRepo:

            tenant_instance = AsyncMock()
            tenant_instance.get_or_create.return_value = MagicMock(id=uuid.uuid4())
            MockTenantRepo.return_value = tenant_instance

            job_instance = AsyncMock()
            job_instance.create.return_value = mock_job
            MockJobRepo.return_value = job_instance

            proc_instance = AsyncMock()
            proc_instance.process_job = AsyncMock()
            MockBatchProc.return_value = proc_instance

            response = client.post("/api/v1/images/ingest", json={"urls": ["https://example.com/1.jpg"]})
            assert response.status_code == 202
            assert response.json()["job_id"] == str(job_id)


class TestListImagesEndpoint:
    """Tests for GET /api/v1/images."""

    def test_list_images_returns_paginated(self, client, mock_db_session):
        """Should return paginated list with total count."""
        mock_img = MagicMock(spec=Image)
        mock_img.id = uuid.uuid4()
        mock_img.tenant_id = uuid.uuid4()
        mock_img.url = "https://example.com/1.jpg"
        mock_img.filename = "1.jpg"
        mock_img.sha256 = "hash123"
        mock_img.source_provider = "unsplash"
        mock_img.source_url = "https://unsplash.com"
        mock_img.license = "Unsplash"
        mock_img.expected_category = "red_fox"
        mock_img.status = "completed"
        mock_img.img_metadata = None
        mock_img.created_at = datetime.now(timezone.utc)

        with patch("app.api.v1.images.ImageRepository") as MockImageRepo, \
             patch("app.api.v1.images.TenantRepository") as MockTenantRepo:

            tenant_instance = AsyncMock()
            tenant_instance.get_or_create.return_value = MagicMock(id=uuid.uuid4())
            MockTenantRepo.return_value = tenant_instance

            img_repo_instance = AsyncMock()
            img_repo_instance.list_images.return_value = ([mock_img], 1)
            MockImageRepo.return_value = img_repo_instance

            response = client.get("/api/v1/images")
            assert response.status_code == 200
            data = response.json()
            assert data["total"] == 1
            assert len(data["items"]) == 1

    def test_list_images_filter_by_status(self, client, mock_db_session):
        """Should support filtering by status."""
        with patch("app.api.v1.images.ImageRepository") as MockImageRepo, \
             patch("app.api.v1.images.TenantRepository") as MockTenantRepo:

            tenant_instance = AsyncMock()
            tenant_instance.get_or_create.return_value = MagicMock(id=uuid.uuid4())
            MockTenantRepo.return_value = tenant_instance

            img_repo_instance = AsyncMock()
            img_repo_instance.list_images.return_value = ([], 0)
            MockImageRepo.return_value = img_repo_instance

            response = client.get("/api/v1/images?status=pending")
            assert response.status_code == 200
            img_repo_instance.list_images.assert_called_once()
            assert img_repo_instance.list_images.call_args.kwargs["status"] == "pending"

    def test_list_images_includes_metadata(self, client, mock_db_session):
        """Should include metadata when available."""
        mock_meta = MagicMock(spec=ImageMetadata)
        mock_meta.subject = "red fox"
        mock_meta.category = "animal"
        mock_meta.attributes = ["orange fur"]
        mock_meta.caption = "A fox"
        mock_meta.confidence = 0.95
        mock_meta.vision_model = "bakllava:7b"
        mock_meta.is_low_confidence = False

        mock_img = MagicMock(spec=Image)
        mock_img.id = uuid.uuid4()
        mock_img.tenant_id = uuid.uuid4()
        mock_img.url = "https://example.com/1.jpg"
        mock_img.filename = "1.jpg"
        mock_img.sha256 = "hash123"
        mock_img.source_provider = "unsplash"
        mock_img.source_url = "https://unsplash.com"
        mock_img.license = "Unsplash"
        mock_img.expected_category = "red_fox"
        mock_img.status = "completed"
        mock_img.img_metadata = mock_meta
        mock_img.created_at = datetime.now(timezone.utc)

        with patch("app.api.v1.images.ImageRepository") as MockImageRepo, \
             patch("app.api.v1.images.TenantRepository") as MockTenantRepo:

            tenant_instance = AsyncMock()
            tenant_instance.get_or_create.return_value = MagicMock(id=uuid.uuid4())
            MockTenantRepo.return_value = tenant_instance

            img_repo_instance = AsyncMock()
            img_repo_instance.list_images.return_value = ([mock_img], 1)
            MockImageRepo.return_value = img_repo_instance

            response = client.get("/api/v1/images")
            assert response.status_code == 200
            data = response.json()
            assert data["items"][0]["img_metadata"]["subject"] == "red fox"


class TestGetImageEndpoint:
    """Tests for GET /api/v1/images/{id}."""

    def test_get_image_success(self, client, mock_db_session):
        """Should return image with metadata."""
        img_id = uuid.uuid4()
        mock_img = MagicMock(spec=Image)
        mock_img.id = img_id
        mock_img.tenant_id = uuid.uuid4()
        mock_img.url = "https://example.com/1.jpg"
        mock_img.filename = "1.jpg"
        mock_img.sha256 = "hash123"
        mock_img.source_provider = "unsplash"
        mock_img.source_url = "https://unsplash.com"
        mock_img.license = "Unsplash"
        mock_img.expected_category = "red_fox"
        mock_img.status = "completed"
        mock_img.img_metadata = None
        mock_img.created_at = datetime.now(timezone.utc)

        with patch("app.api.v1.images.ImageRepository") as MockImageRepo, \
             patch("app.api.v1.images.TenantRepository") as MockTenantRepo:

            tenant_instance = AsyncMock()
            tenant_instance.get_or_create.return_value = MagicMock(id=uuid.uuid4())
            MockTenantRepo.return_value = tenant_instance

            img_repo_instance = AsyncMock()
            img_repo_instance.get_by_id.return_value = mock_img
            MockImageRepo.return_value = img_repo_instance

            response = client.get(f"/api/v1/images/{img_id}")
            assert response.status_code == 200
            assert response.json()["id"] == str(img_id)

    def test_get_image_not_found(self, client, mock_db_session):
        """Non-existent image should return 404."""
        img_id = uuid.uuid4()
        with patch("app.api.v1.images.ImageRepository") as MockImageRepo, \
             patch("app.api.v1.images.TenantRepository") as MockTenantRepo:

            tenant_instance = AsyncMock()
            tenant_instance.get_or_create.return_value = MagicMock(id=uuid.uuid4())
            MockTenantRepo.return_value = tenant_instance

            img_repo_instance = AsyncMock()
            img_repo_instance.get_by_id.return_value = None
            MockImageRepo.return_value = img_repo_instance

            response = client.get(f"/api/v1/images/{img_id}")
            assert response.status_code == 404

    def test_get_image_invalid_uuid(self, client):
        """Invalid UUID should return 422."""
        response = client.get("/api/v1/images/invalid-uuid-string")
        assert response.status_code == 422


class TestJobStatusEndpoint:
    """Tests for GET /api/v1/jobs/{id}."""

    def test_get_job_success(self, client, mock_db_session):
        """Should return job with progress."""
        job_id = uuid.uuid4()
        mock_job = MagicMock(spec=Job)
        mock_job.id = job_id
        mock_job.tenant_id = uuid.uuid4()
        mock_job.type = "image_ingestion"
        mock_job.status = "completed"
        mock_job.progress = 100
        mock_job.payload = {"urls": ["https://example.com/1.jpg"]}
        mock_job.error = None
        mock_job.created_at = datetime.now(timezone.utc)

        with patch("app.api.v1.jobs.JobRepository") as MockJobRepo, \
             patch("app.api.v1.jobs.TenantRepository") as MockTenantRepo:

            tenant_instance = AsyncMock()
            tenant_instance.get_or_create.return_value = MagicMock(id=uuid.uuid4())
            MockTenantRepo.return_value = tenant_instance

            job_repo_instance = AsyncMock()
            job_repo_instance.get_by_id.return_value = mock_job
            MockJobRepo.return_value = job_repo_instance

            response = client.get(f"/api/v1/jobs/{job_id}")
            assert response.status_code == 200
            assert response.json()["progress"] == 100

    def test_get_job_not_found(self, client, mock_db_session):
        """Non-existent job should return 404."""
        job_id = uuid.uuid4()
        with patch("app.api.v1.jobs.JobRepository") as MockJobRepo, \
             patch("app.api.v1.jobs.TenantRepository") as MockTenantRepo:

            tenant_instance = AsyncMock()
            tenant_instance.get_or_create.return_value = MagicMock(id=uuid.uuid4())
            MockTenantRepo.return_value = tenant_instance

            job_repo_instance = AsyncMock()
            job_repo_instance.get_by_id.return_value = None
            MockJobRepo.return_value = job_repo_instance

            response = client.get(f"/api/v1/jobs/{job_id}")
            assert response.status_code == 404


class TestCostLogEndpoint:
    """Tests for GET /api/v1/costs."""

    def test_get_costs_returns_list(self, client, mock_db_session):
        """Should return paginated cost records."""
        mock_cost = MagicMock(spec=Cost)
        mock_cost.id = uuid.uuid4()
        mock_cost.tenant_id = uuid.uuid4()
        mock_cost.operation = "vision_classification"
        mock_cost.model = "bakllava:7b"
        mock_cost.related_type = "image"
        mock_cost.related_id = uuid.uuid4()
        mock_cost.tokens_input = 100
        mock_cost.tokens_output = 50
        mock_cost.cost_usd = 0.0
        mock_cost.status = "success"
        mock_cost.created_at = datetime.now(timezone.utc)

        with patch("app.api.v1.costs.CostRepository") as MockCostRepo, \
             patch("app.api.v1.costs.TenantRepository") as MockTenantRepo:

            tenant_instance = AsyncMock()
            tenant_instance.get_or_create.return_value = MagicMock(id=uuid.uuid4())
            MockTenantRepo.return_value = tenant_instance

            cost_repo_instance = AsyncMock()
            cost_repo_instance.list_costs.return_value = ([mock_cost], 1, 0.0)
            MockCostRepo.return_value = cost_repo_instance

            response = client.get("/api/v1/costs")
            assert response.status_code == 200
            data = response.json()
            assert data["total"] == 1
            assert data["total_cost_usd"] == 0.0

    def test_get_costs_includes_total(self, client, mock_db_session):
        """Should include total count and total cost sum."""
        with patch("app.api.v1.costs.CostRepository") as MockCostRepo, \
             patch("app.api.v1.costs.TenantRepository") as MockTenantRepo:

            tenant_instance = AsyncMock()
            tenant_instance.get_or_create.return_value = MagicMock(id=uuid.uuid4())
            MockTenantRepo.return_value = tenant_instance

            cost_repo_instance = AsyncMock()
            cost_repo_instance.list_costs.return_value = ([], 5, 0.0)
            MockCostRepo.return_value = cost_repo_instance

            response = client.get("/api/v1/costs")
            assert response.status_code == 200
            assert response.json()["total"] == 5

    def test_get_costs_filter_by_operation(self, client, mock_db_session):
        """Should support filtering by operation type."""
        with patch("app.api.v1.costs.CostRepository") as MockCostRepo, \
             patch("app.api.v1.costs.TenantRepository") as MockTenantRepo:

            tenant_instance = AsyncMock()
            tenant_instance.get_or_create.return_value = MagicMock(id=uuid.uuid4())
            MockTenantRepo.return_value = tenant_instance

            cost_repo_instance = AsyncMock()
            cost_repo_instance.list_costs.return_value = ([], 0, 0.0)
            MockCostRepo.return_value = cost_repo_instance

            response = client.get("/api/v1/costs?operation=vision_classification")
            assert response.status_code == 200
            assert cost_repo_instance.list_costs.call_args.kwargs["operation"] == "vision_classification"


class TestAPIValidation:
    """Tests for API input validation (4xx errors)."""

    def test_invalid_uuid_returns_422(self, client):
        """Invalid UUID in path should return 422, not 500."""
        response = client.get("/api/v1/images/not-a-uuid")
        assert response.status_code == 422

    def test_malformed_json_returns_422(self, client):
        """Malformed JSON body should return 422."""
        response = client.post(
            "/api/v1/images/ingest",
            content="{bad_json: ",
            headers={"Content-Type": "application/json"},
        )
        assert response.status_code == 422

    def test_missing_required_field_returns_422(self, client):
        """Missing required field should return 422."""
        response = client.post("/api/v1/posts", json={})
        assert response.status_code == 422

    def test_no_internal_errors_leaked(self, client):
        """Error responses should not leak stack traces or secrets."""
        response = client.get("/api/v1/images/invalid-uuid-format")
        assert response.status_code == 422
        body = response.json()
        assert "traceback" not in body
        assert "secret" not in str(body).lower()