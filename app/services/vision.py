"""Vision processing service with Ollama integration and schema validation."""

import base64
import hashlib
import json
import logging
from typing import Optional
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

import httpx
from pydantic import ValidationError

from app.core.config import settings
from app.schemas.vision import VisionOutput

logger = logging.getLogger(__name__)


class VisionProcessingError(Exception):
    """Exception for vision processing failures."""
    pass


class VisionSchemaValidationError(VisionProcessingError):
    """Exception for schema validation failures."""
    pass


class VisionService:
    """Service for processing images through Ollama vision model with schema validation."""

    def __init__(self):
        self.base_url = settings.ollama_base_url.rstrip("/")
        self.model = settings.vision_model
        self.client = httpx.AsyncClient(timeout=120.0)

    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()

    def _encode_image(self, image_bytes: bytes) -> str:
        """Encode image bytes to base64."""
        return base64.b64encode(image_bytes).decode("utf-8")

    def _build_prompt(self) -> str:
        """Build the prompt for structured vision output."""
        return """Analyze this image and provide a structured JSON response with the following fields:
- subject: The primary subject (e.g., "red fox", "gray wolf", "golden retriever")
- category: High-level category (e.g., "animal", "bird", "vehicle")
- attributes: List of visual attributes (e.g., ["orange fur", "wild", "forest", "standing"])
- caption: Natural language description (e.g., "A red fox standing in a forest clearing")
- confidence: Your confidence score from 0.0 to 1.0

Return ONLY valid JSON. No additional text or explanation."""

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=4),
        retry=retry_if_exception_type((httpx.RequestError, httpx.HTTPStatusError, VisionSchemaValidationError)),
        reraise=True,
    )
    async def _call_vision_model(self, image_base64: str) -> dict:
        """Call Ollama vision model with retry logic."""
        payload = {
            "model": self.model,
            "prompt": self._build_prompt(),
            "images": [image_base64],
            "stream": False,
            "format": "json",
            "options": {
                "temperature": 0.1,
            },
        }

        try:
            response = await self.client.post(
                f"{self.base_url}/api/generate",
                json=payload,
            )
            response.raise_for_status()
            result = response.json()

            # Parse the response
            response_text = result.get("response", "").strip()
            if not response_text:
                raise VisionProcessingError("Empty response from vision model")

            try:
                parsed = json.loads(response_text)
            except json.JSONDecodeError as e:
                logger.warning(f"Failed to parse vision model JSON: {response_text[:200]}")
                raise VisionSchemaValidationError(f"Invalid JSON from model: {e}")

            return parsed

        except httpx.HTTPStatusError as e:
            logger.error(f"Ollama API error: {e.response.status_code} - {e.response.text}")
            raise VisionProcessingError(f"Ollama API error: {e.response.status_code}")
        except httpx.RequestError as e:
            logger.error(f"Ollama connection error: {e}")
            raise VisionProcessingError(f"Ollama connection error: {e}")

    def _validate_vision_output(self, raw_output: dict) -> VisionOutput:
        """Validate raw model output against VisionOutput schema."""
        try:
            return VisionOutput(**raw_output)
        except ValidationError as e:
            logger.warning(f"Vision output validation failed: {e.errors()}")
            raise VisionSchemaValidationError(f"Schema validation failed: {e.errors()}")

    async def process_image(self, image_bytes: bytes) -> VisionOutput:
        """Process image through vision model with full validation and retries.

        Args:
            image_bytes: Raw image bytes

        Returns:
            Validated VisionOutput

        Raises:
            VisionProcessingError: If processing fails after retries
            VisionSchemaValidationError: If output fails schema validation after retries
        """
        image_base64 = self._encode_image(image_bytes)

        # Call vision model with retries
        raw_output = await self._call_vision_model(image_base64)

        # Validate against schema
        validated = self._validate_vision_output(raw_output)

        logger.info(f"Vision processing successful: subject={validated.subject}, confidence={validated.confidence}")
        return validated

    def is_low_confidence(self, confidence: float, threshold: float = 0.70) -> bool:
        """Check if confidence is below threshold."""
        return confidence < threshold


async def get_vision_service() -> VisionService:
    """Dependency for FastAPI to get vision service."""
    service = VisionService()
    try:
        yield service
    finally:
        await service.close()