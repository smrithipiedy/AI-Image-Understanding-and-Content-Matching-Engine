"""Embedding service for generating text embeddings using nomic-embed-text."""

import logging
from typing import List, Optional
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from app.core.config import settings

logger = logging.getLogger(__name__)


class EmbeddingError(Exception):
    """Exception raised when embedding generation fails."""
    pass


class EmbeddingService:
    """Service for generating text embeddings with Ollama."""

    def __init__(self, ollama_base_url: Optional[str] = None, model: Optional[str] = None):
        self.base_url = (ollama_base_url or settings.ollama_base_url).rstrip("/")
        self.model = model or settings.embedding_model
        self.embeddings_url = f"{self.base_url}/api/embeddings"
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=30.0)
        return self._client

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type(EmbeddingError),
        reraise=True,
    )
    async def generate_embedding(self, text: str) -> List[float]:
        """Generate 768-dimensional float embedding for given text."""
        if not text or not text.strip():
            raise EmbeddingError("Text for embedding cannot be empty")

        payload = {
            "model": self.model,
            "prompt": text,
        }

        try:
            client = await self._get_client()
            response = await client.post(self.embeddings_url, json=payload)
            response.raise_for_status()

            data = response.json()
            embedding = data.get("embedding")

            if not embedding or not isinstance(embedding, list):
                raise EmbeddingError(f"Invalid embedding response format from model {self.model}")

            return [float(val) for val in embedding]

        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error calling embedding model {self.model}: {e}")
            raise EmbeddingError(f"HTTP error from Ollama embedding API: {e}") from e
        except httpx.RequestError as e:
            logger.error(f"Network error calling embedding model {self.model}: {e}")
            raise EmbeddingError(f"Network error calling Ollama embedding API: {e}") from e
        except Exception as e:
            if isinstance(e, EmbeddingError):
                raise
            logger.error(f"Unexpected error in embedding generation: {e}")
            raise EmbeddingError(f"Unexpected error in embedding generation: {e}") from e
