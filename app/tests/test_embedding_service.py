"""Tests for EmbeddingService text embedding generation."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import httpx

from app.services.embedding import EmbeddingService, EmbeddingError


class TestEmbeddingService:
    """Tests for EmbeddingService."""

    @pytest.mark.asyncio
    async def test_generate_embedding_success(self):
        """Should return float vector embedding from Ollama."""
        service = EmbeddingService(ollama_base_url="http://localhost:11434", model="nomic-embed-text")

        fake_vector = [0.1] * 768
        mock_response = MagicMock()
        mock_response.json.return_value = {"embedding": fake_vector}
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)

        with patch.object(service, "_get_client", return_value=mock_client):
            vector = await service.generate_embedding("A beautiful red fox in the snow")
            assert len(vector) == 768
            assert vector[0] == 0.1

    @pytest.mark.asyncio
    async def test_generate_embedding_empty_text_raises(self):
        """Should raise EmbeddingError when text is empty."""
        service = EmbeddingService()
        with pytest.raises(EmbeddingError):
            await service.generate_embedding("   ")

    @pytest.mark.asyncio
    async def test_generate_embedding_http_error(self):
        """Should raise EmbeddingError on HTTP failure."""
        service = EmbeddingService()

        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError("500 Error", request=MagicMock(), response=MagicMock(status_code=500))

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)

        with patch.object(service, "_get_client", return_value=mock_client):
            with pytest.raises(EmbeddingError):
                await service.generate_embedding("Test text")
