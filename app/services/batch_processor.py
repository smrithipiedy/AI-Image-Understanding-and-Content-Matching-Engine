"""Background batch processor service for processing images with vision model."""

import asyncio
import logging
import uuid
from typing import List, Optional
import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.repositories import (
    ImageRepository,
    ImageMetadataRepository,
    JobRepository,
)
from app.models import ImageStatus, JobStatus
from app.services.vision import VisionService, VisionProcessingError, VisionSchemaValidationError
from app.services.cost import CostService

logger = logging.getLogger(__name__)


class BatchProcessor:
    """Batch image processor handling background job processing."""

    def __init__(
        self,
        session: AsyncSession,
        vision_service: Optional[VisionService] = None,
        cost_service: Optional[CostService] = None,
        confidence_threshold: float = 0.70,
        max_retries: int = 3,
    ):
        self.session = session
        self.image_repo = ImageRepository(session)
        self.metadata_repo = ImageMetadataRepository(session)
        self.job_repo = JobRepository(session)
        self.vision_service = vision_service or VisionService()
        self.cost_service = cost_service or CostService(session)
        self.confidence_threshold = confidence_threshold
        self.max_retries = max_retries

    async def fetch_image_bytes(self, client: httpx.AsyncClient, url: str) -> bytes:
        """Fetch image bytes from URL."""
        response = await client.get(url, follow_redirects=True, timeout=15.0)
        response.raise_for_status()
        return response.content

    async def process_single_image(
        self,
        tenant_id: uuid.UUID,
        image_id: uuid.UUID,
        image_bytes: bytes,
    ) -> bool:
        """Process a single image through vision service, record metadata & costs.

        Returns True on success, False on failure.
        """
        try:
            # Call vision service
            vision_output = await self.vision_service.process_image(image_bytes)

            # Check low confidence
            is_low_conf = self.vision_service.is_low_confidence(
                vision_output.confidence,
                threshold=self.confidence_threshold,
            )

            # Create metadata record
            await self.metadata_repo.create(
                image_id=image_id,
                subject=vision_output.subject,
                category=vision_output.category,
                attributes=vision_output.attributes,
                caption=vision_output.caption,
                confidence=vision_output.confidence,
                vision_model=settings.vision_model,
                is_low_confidence=is_low_conf,
            )

            # Estimate token usage (rough approximation or default)
            approx_input_tokens = max(len(image_bytes) // 100, 100)
            approx_output_tokens = 100
            await self.cost_service.record_vision_cost(
                tenant_id=tenant_id,
                related_type="image",
                related_id=image_id,
                input_tokens=approx_input_tokens,
                output_tokens=approx_output_tokens,
                status="success",
            )

            # Update image status to COMPLETED
            await self.image_repo.update_status(image_id, ImageStatus.COMPLETED)
            return True

        except (VisionProcessingError, VisionSchemaValidationError, Exception) as e:
            logger.error(f"Failed processing image {image_id}: {e}")
            await self.cost_service.record_failed_cost(
                tenant_id=tenant_id,
                operation="vision_classification",
                model=settings.vision_model,
                related_type="image",
                related_id=image_id,
            )
            await self.image_repo.update_status(image_id, ImageStatus.FAILED)
            return False

    async def process_job(self, job_id: uuid.UUID, tenant_id: uuid.UUID) -> None:
        """Process a batch job by ID."""
        job = await self.job_repo.get_by_id(job_id, tenant_id)
        if not job:
            logger.error(f"Job {job_id} not found for tenant {tenant_id}")
            return

        urls: List[str] = job.payload.get("urls", [])
        if not urls:
            await self.job_repo.update_status(job_id, JobStatus.COMPLETED, progress=100)
            return

        await self.job_repo.update_status(job_id, JobStatus.PROCESSING, progress=0)
        total = len(urls)
        processed = 0

        async with httpx.AsyncClient() as client:
            for idx, url in enumerate(urls):
                image = await self.image_repo.get_by_url(url, tenant_id)
                if not image:
                    # Create pending image record if missing
                    filename = url.split("/")[-1] or f"img_{uuid.uuid4().hex[:8]}.jpg"
                    image = await self.image_repo.create(
                        tenant_id=tenant_id,
                        url=url,
                        filename=filename,
                        sha256="",
                        source_provider="batch_processor",
                        source_url=url,
                        license="unknown",
                    )

                # Skip if already completed
                if image.status == ImageStatus.COMPLETED:
                    processed += 1
                    progress = int((processed / total) * 100)
                    await self.job_repo.update_status(job_id, JobStatus.PROCESSING, progress=progress)
                    continue

                # Retry loop with backoff for fetching & processing image
                success = False
                for attempt in range(1, self.max_retries + 1):
                    try:
                        image_bytes = await self.fetch_image_bytes(client, url)
                        success = await self.process_single_image(tenant_id, image.id, image_bytes)
                        if success:
                            break
                    except Exception as e:
                        logger.warning(f"Attempt {attempt} failed for {url}: {e}")
                    if not success and attempt < self.max_retries:
                        await asyncio.sleep(2 ** (attempt - 1))

                if not success:
                    await self.image_repo.update_status(image.id, ImageStatus.FAILED)

                processed += 1
                progress = int((processed / total) * 100)
                await self.job_repo.update_status(job_id, JobStatus.PROCESSING, progress=progress)

        await self.job_repo.update_status(job_id, JobStatus.COMPLETED, progress=100)
