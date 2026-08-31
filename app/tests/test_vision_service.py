"""Tests for vision service - TDD: written BEFORE implementation."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import httpx
import json

from app.services.vision import VisionService, VisionProcessingError, VisionSchemaValidationError
from app.schemas.vision import VisionOutput


class TestVisionService:
    """Tests for VisionService."""

@pytest.fixture
def vision_service():
    """Create a VisionService instance for testing."""
    service = VisionService()
    service.base_url = "http://test-ollama:11434"
    service.model = "bakllava:7b"
    return service


@pytest.fixture
def sample_image_bytes():
    """Sample image bytes for testing."""
    return b"fake-image-bytes"


@pytest.fixture
def valid_vision_response():
    """Valid vision model response."""
    return {
        "subject": "red fox",
        "category": "animal",
        "attributes": ["orange fur", "wild", "forest"],
        "caption": "A red fox standing in a forest",
        "confidence": 0.94,
    }


@pytest.fixture
def low_confidence_vision_response():
    """Low confidence vision model response."""
    return {
        "subject": "gray wolf",
        "category": "animal",
        "attributes": ["gray fur", "wild"],
        "caption": "A wolf in the snow",
        "confidence": 0.45,
    }


class TestVisionService:
    """Tests for VisionService."""

    @pytest.mark.asyncio
    async def test_process_image_success(self, vision_service, sample_image_bytes, valid_vision_response):
        """Successful vision processing should return validated output."""
        with patch.object(vision_service.client, 'post', new_callable=AsyncMock) as mock_post:
            mock_response = MagicMock()
            mock_response.json.return_value = {"response": json.dumps(valid_vision_response)}
            mock_response.raise_for_status = MagicMock()
            mock_post.return_value = mock_response

            result = await vision_service.process_image(sample_image_bytes)

            assert isinstance(result, VisionOutput)
            assert result.subject == "red fox"
            assert result.confidence == 0.94
            mock_post.assert_called_once()

    @pytest.mark.asyncio
    async def test_process_image_validates_schema(self, vision_service, sample_image_bytes, valid_vision_response):
        """Vision output must pass schema validation."""
        with patch.object(vision_service.client, 'post', new_callable=AsyncMock) as mock_post:
            mock_response = MagicMock()
            mock_response.json.return_value = {"response": json.dumps(valid_vision_response)}
            mock_response.raise_for_status = MagicMock()
            mock_post.return_value = mock_response

            result = await vision_service.process_image(sample_image_bytes)

            assert isinstance(result, VisionOutput)
            # Verify all required fields present
            assert result.subject
            assert result.category
            assert isinstance(result.attributes, list)
            assert result.caption
            assert 0.0 <= result.confidence <= 1.0

    @pytest.mark.asyncio
    async def test_process_image_retry_on_network_error(self, vision_service, sample_image_bytes, valid_vision_response):
        """Should retry on network errors (up to 3 attempts)."""
        with patch.object(vision_service.client, 'post', new_callable=AsyncMock) as mock_post:
            # First two calls fail, third succeeds
            mock_post.side_effect = [
                httpx.RequestError("Connection failed"),
                httpx.RequestError("Connection failed"),
                MagicMock(
                    json=MagicMock(return_value={"response": json.dumps(valid_vision_response)}),
                    raise_for_status=MagicMock()
                ),
            ]

            result = await vision_service.process_image(sample_image_bytes)

            assert isinstance(result, VisionOutput)
            assert result.subject == "red fox"
            assert mock_post.call_count == 3

    @pytest.mark.asyncio
    async def test_process_image_retry_on_http_error(self, vision_service, sample_image_bytes, valid_vision_response):
        """Should retry on HTTP 5xx errors."""
        with patch.object(vision_service.client, 'post', new_callable=AsyncMock) as mock_post:
            mock_post.side_effect = [
                httpx.HTTPStatusError("Server Error", request=MagicMock(), response=MagicMock(status_code=500)),
                MagicMock(
                    json=MagicMock(return_value={"response": json.dumps(valid_vision_response)}),
                    raise_for_status=MagicMock()
                ),
            ]

            result = await vision_service.process_image(sample_image_bytes)

            assert isinstance(result, VisionOutput)
            assert mock_post.call_count == 2

    @pytest.mark.asyncio
    async def test_process_image_fails_after_max_retries(self, vision_service, sample_image_bytes):
        """Should raise VisionProcessingError after max retries exhausted."""
        with patch.object(vision_service.client, 'post', new_callable=AsyncMock) as mock_post:
            mock_post.side_effect = httpx.RequestError("Persistent connection failure")

            with pytest.raises((VisionProcessingError, httpx.RequestError)) as exc_info:
                await vision_service.process_image(sample_image_bytes)

            assert mock_post.call_count == 3  # 3 attempts

    @pytest.mark.asyncio
    async def test_process_image_rejects_invalid_json(self, vision_service, sample_image_bytes):
        """Should raise VisionSchemaValidationError for invalid JSON from model."""
        with patch.object(vision_service.client, 'post', new_callable=AsyncMock) as mock_post:
            mock_response = MagicMock()
            mock_response.json.return_value = {"response": "not valid json {{{"}
            mock_response.raise_for_status = MagicMock()
            mock_post.return_value = mock_response

            with pytest.raises(VisionSchemaValidationError) as exc_info:
                await vision_service.process_image(sample_image_bytes)

            assert "invalid json" in str(exc_info.value).lower() or "schema validation failed" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_process_image_rejects_schema_violations(self, vision_service, sample_image_bytes):
        """Should reject model output that violates schema (e.g., missing fields, invalid confidence)."""
        invalid_response = {
            "subject": "",  # Empty subject - invalid
            "category": "animal",
            "attributes": [],
            "caption": "A fox",
            "confidence": 0.5,
        }
        with patch.object(vision_service.client, 'post', new_callable=AsyncMock) as mock_post:
            mock_response = MagicMock()
            mock_response.json.return_value = {"response": json.dumps(invalid_response)}
            mock_response.raise_for_status = MagicMock()
            mock_post.return_value = mock_response

            with pytest.raises(VisionSchemaValidationError) as exc_info:
                await vision_service.process_image(sample_image_bytes)

            assert "schema validation failed" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_process_image_retry_on_schema_validation_failure(self, vision_service, sample_image_bytes, valid_vision_response):
        """Should retry when schema validation fails (model might fix output on retry)."""
        with patch.object(vision_service.client, 'post', new_callable=AsyncMock) as mock_post:
            # First response has invalid confidence, second is valid
            mock_post.side_effect = [
                MagicMock(
                    json=MagicMock(return_value={"response": json.dumps({**valid_vision_response, "confidence": 1.5})}),
                    raise_for_status=MagicMock()
                ),
                MagicMock(
                    json=MagicMock(return_value={"response": json.dumps(valid_vision_response)}),
                    raise_for_status=MagicMock()
                ),
            ]

            result = await vision_service.process_image(sample_image_bytes)

            assert isinstance(result, VisionOutput)
            assert result.confidence == 0.94
            assert mock_post.call_count == 2

    @pytest.mark.asyncio
    async def test_is_low_confidence_true(self, vision_service):
        """is_low_confidence should return True for confidence below threshold."""
        assert vision_service.is_low_confidence(0.55, threshold=0.70) is True
        assert vision_service.is_low_confidence(0.69, threshold=0.70) is True
        assert vision_service.is_low_confidence(0.0, threshold=0.70) is True

    @pytest.mark.asyncio
    async def test_is_low_confidence_false(self, vision_service):
        """is_low_confidence should return False for confidence at or above threshold."""
        assert vision_service.is_low_confidence(0.70, threshold=0.70) is False
        assert vision_service.is_low_confidence(0.85, threshold=0.70) is False
        assert vision_service.is_low_confidence(1.0, threshold=0.70) is False

    @pytest.mark.asyncio
    async def test_encode_image(self, vision_service):
        """_encode_image should return base64 string."""
        image_bytes = b"test image data"
        encoded = vision_service._encode_image(image_bytes)
        assert isinstance(encoded, str)
        # Verify it's valid base64
        import base64
        decoded = base64.b64decode(encoded)
        assert decoded == image_bytes

    @pytest.mark.asyncio
    async def test_build_prompt(self, vision_service):
        """_build_prompt should return structured prompt."""
        prompt = vision_service._build_prompt()
        assert "subject" in prompt.lower()
        assert "category" in prompt.lower()
        assert "attributes" in prompt.lower()
        assert "caption" in prompt.lower()
        assert "confidence" in prompt.lower()
        assert "json" in prompt.lower()

    @pytest.mark.asyncio
    async def test_close_client(self, vision_service):
        """close should close the HTTP client."""
        with patch.object(vision_service.client, 'aclose', new_callable=AsyncMock) as mock_close:
            await vision_service.close()
            mock_close.assert_called_once()


class TestVisionServiceIntegration:
    """Integration-style tests for vision service behavior."""

    @pytest.mark.asyncio
    async def test_low_confidence_image_flagged(self, vision_service, sample_image_bytes, low_confidence_vision_response):
        """Low confidence result should be detectable via is_low_confidence."""
        with patch.object(vision_service.client, 'post', new_callable=AsyncMock) as mock_post:
            mock_response = MagicMock()
            mock_response.json.return_value = {"response": json.dumps(low_confidence_vision_response)}
            mock_response.raise_for_status = MagicMock()
            mock_post.return_value = mock_response

            result = await vision_service.process_image(sample_image_bytes)

            # The service returns valid output, but confidence is low
            assert result.confidence == 0.45
            # Caller should use is_low_confidence to flag
            assert vision_service.is_low_confidence(result.confidence, threshold=0.70) is True

    @pytest.mark.asyncio
    async def test_malformed_model_output_handled_gracefully(self, vision_service, sample_image_bytes):
        """Malformed model output should not crash, should raise validation error."""
        malformed_responses = [
            '{"subject": "fox"',  # Incomplete JSON
            'not json at all',
            '{"subject": "fox", "confidence": "high"}',  # Wrong type
            '{}',  # Missing required fields
        ]

        for malformed in malformed_responses:
            with patch.object(vision_service.client, 'post', new_callable=AsyncMock) as mock_post:
                mock_response = MagicMock()
                mock_response.json.return_value = {"response": malformed}
                mock_response.raise_for_status = MagicMock()
                mock_post.return_value = mock_response

                with pytest.raises((VisionSchemaValidationError, VisionProcessingError)):
                    await vision_service.process_image(sample_image_bytes)