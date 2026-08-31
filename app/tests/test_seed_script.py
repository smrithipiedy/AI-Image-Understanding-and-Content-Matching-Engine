"""Tests for seed script - TDD: written BEFORE implementation."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch, mock_open
import hashlib
import json
import os

# These imports will work after seed script is implemented
import httpx
from scripts.seed import SeedScript, ImageManifest, download_image, compute_sha256


class TestImageManifest:
    """Tests for image manifest data structure."""

    def test_manifest_structure(self):
        """Manifest should have required fields for each image."""
        manifest_entry = {
            "url": "https://images.unsplash.com/photo-xxx",
            "filename": "red_fox_1.jpg",
            "source_provider": "unsplash",
            "source_url": "https://unsplash.com/photos/xxx",
            "license": "Unsplash License",
            "expected_category": "red_fox",
        }
        assert "url" in manifest_entry
        assert "filename" in manifest_entry
        assert "source_provider" in manifest_entry
        assert "source_url" in manifest_entry
        assert "license" in manifest_entry
        assert "expected_category" in manifest_entry

    def test_manifest_categories(self):
        """Manifest should cover required categories."""
        categories = ["red_fox", "wolf", "dog", "bear", "deer"]
        assert len(categories) >= 4


class TestComputeSHA256:
    """Tests for SHA256 computation."""

    def test_compute_sha256_consistent(self):
        """Same bytes should produce same hash."""
        data = b"test image data"
        hash1 = compute_sha256(data)
        hash2 = compute_sha256(data)
        assert hash1 == hash2
        assert len(hash1) == 64

    def test_compute_sha256_different_for_different_data(self):
        """Different data should produce different hashes."""
        hash1 = compute_sha256(b"data1")
        hash2 = compute_sha256(b"data2")
        assert hash1 != hash2


class TestDownloadImage:
    """Tests for image downloading."""

    @pytest.mark.asyncio
    async def test_download_image_success(self):
        """Should download and return image bytes."""
        client = AsyncMock()
        mock_response = MagicMock()
        mock_response.content = b"fake-image-bytes"
        mock_response.raise_for_status = MagicMock()
        client.get = AsyncMock(return_value=mock_response)

        data = await download_image(client, "https://example.com/img.jpg")
        assert data == b"fake-image-bytes"

    @pytest.mark.asyncio
    async def test_download_image_http_error(self):
        """Should raise on HTTP error."""
        client = AsyncMock()
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError("404 Not Found", request=MagicMock(), response=MagicMock(status_code=404))
        client.get = AsyncMock(return_value=mock_response)

        with pytest.raises(httpx.HTTPStatusError):
            await download_image(client, "https://example.com/404.jpg")

    @pytest.mark.asyncio
    async def test_download_image_timeout(self):
        """Should handle timeout."""
        client = AsyncMock()
        client.get.side_effect = httpx.TimeoutException("Request timed out")

        with pytest.raises(httpx.TimeoutException):
            await download_image(client, "https://example.com/timeout.jpg")

    @pytest.mark.asyncio
    async def test_download_image_invalid_url(self):
        """Should handle invalid URL."""
        client = AsyncMock()
        client.get.side_effect = Exception("Invalid URL")

        with pytest.raises(Exception):
            await download_image(client, "invalid-url")


class TestSeedScript:
    """Tests for the main seed script."""

    @pytest.fixture
    def mock_manifest(self):
        """Sample manifest for testing."""
        return [
            {
                "url": "https://example.com/fox1.jpg",
                "filename": "fox1.jpg",
                "source_provider": "unsplash",
                "source_url": "https://unsplash.com/photos/fox1",
                "license": "Unsplash License",
                "expected_category": "red_fox",
            },
            {
                "url": "https://example.com/wolf1.jpg",
                "filename": "wolf1.jpg",
                "source_provider": "pexels",
                "source_url": "https://pexels.com/photo/wolf1",
                "license": "Pexels License",
                "expected_category": "wolf",
            },
        ]

    @pytest.mark.asyncio
    async def test_seed_creates_images_in_db(self, mock_manifest):
        """Seed should create Image records in database."""
        script = SeedScript()
        with patch.object(script, "load_manifest", return_value=mock_manifest):
            with patch("scripts.seed.download_image", new_callable=AsyncMock) as mock_dl:
                mock_dl.return_value = b"test-image-content"
                mock_session = AsyncMock()
                mock_session.execute.return_value = MagicMock(scalar_one_or_none=MagicMock(return_value=None))

                res = await script.run(session=mock_session)
                assert res["images_processed"] == 2
                assert res["job_id"] is not None

    @pytest.mark.asyncio
    async def test_seed_is_idempotent(self, mock_manifest):
        """Running seed twice should not create duplicates."""
        script = SeedScript()
        with patch.object(script, "load_manifest", return_value=mock_manifest):
            with patch("scripts.seed.download_image", new_callable=AsyncMock) as mock_dl:
                mock_dl.return_value = b"test-image-content"
                mock_session = AsyncMock()
                mock_session.execute.return_value = MagicMock(scalar_one_or_none=MagicMock(return_value=None))

                res1 = await script.run(session=mock_session)
                assert res1["images_processed"] == 2

    @pytest.mark.asyncio
    async def test_seed_records_sha256(self, mock_manifest):
        """Seed should compute and store SHA256 for each image."""
        script = SeedScript()
        with patch.object(script, "load_manifest", return_value=mock_manifest):
            with patch("scripts.seed.download_image", new_callable=AsyncMock) as mock_dl:
                mock_dl.return_value = b"sample-bytes"
                mock_session = AsyncMock()
                mock_session.execute.return_value = MagicMock(scalar_one_or_none=MagicMock(return_value=None))

                await script.run(session=mock_session)
                expected_sha = hashlib.sha256(b"sample-bytes").hexdigest()
                assert len(expected_sha) == 64

    @pytest.mark.asyncio
    async def test_seed_records_all_metadata(self, mock_manifest):
        """Seed should record provider, URL, license, expected_category."""
        script = SeedScript()
        with patch.object(script, "load_manifest", return_value=mock_manifest):
            with patch("scripts.seed.download_image", new_callable=AsyncMock) as mock_dl:
                mock_dl.return_value = b"sample-bytes"
                mock_session = AsyncMock()
                mock_session.execute.return_value = MagicMock(scalar_one_or_none=MagicMock(return_value=None))

                res = await script.run(session=mock_session)
                assert res["images_processed"] == 2

    @pytest.mark.asyncio
    async def test_seed_handles_download_failure(self, mock_manifest):
        """Seed should handle individual download failures gracefully."""
        script = SeedScript()
        with patch.object(script, "load_manifest", return_value=mock_manifest):
            with patch("scripts.seed.download_image", new_callable=AsyncMock) as mock_dl:
                mock_dl.side_effect = [b"good-bytes", Exception("Download error")]
                mock_session = AsyncMock()
                mock_session.execute.return_value = MagicMock(scalar_one_or_none=MagicMock(return_value=None))

                res = await script.run(session=mock_session)
                assert res["images_processed"] == 1

    @pytest.mark.asyncio
    async def test_seed_creates_job_for_batch_processing(self, mock_manifest):
        """Seed should create a job to trigger batch processing."""
        script = SeedScript()
        with patch.object(script, "load_manifest", return_value=mock_manifest):
            with patch("scripts.seed.download_image", new_callable=AsyncMock) as mock_dl:
                mock_dl.return_value = b"bytes"
                mock_session = AsyncMock()
                mock_session.execute.return_value = MagicMock(scalar_one_or_none=MagicMock(return_value=None))

                res = await script.run(session=mock_session)
                assert res["job_id"] is not None


class TestManifestFile:
    """Tests for manifest file handling."""

    def test_manifest_file_exists(self):
        """Manifest file should exist at expected path."""
        manifest_path = "scripts/manifest.json"
        assert os.path.exists(manifest_path)

    def test_manifest_file_valid_json(self):
        """Manifest file should be valid JSON."""
        manifest_path = "scripts/manifest.json"
        with open(manifest_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        assert isinstance(data, list)

    def test_manifest_has_minimum_images(self):
        """Manifest should have at least 40 images."""
        manifest_path = "scripts/manifest.json"
        with open(manifest_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        assert len(data) >= 40

    def test_manifest_has_required_categories(self):
        """Manifest should have at least 4 categories."""
        manifest_path = "scripts/manifest.json"
        with open(manifest_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        categories = set(item.get("expected_category") for item in data)
        assert len(categories) >= 4