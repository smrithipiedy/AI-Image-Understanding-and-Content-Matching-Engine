"""Seed script to populate database with seed images dataset."""

import asyncio
import hashlib
import json
import logging
import os
import uuid
from typing import Any, List, Optional, Dict
import httpx
from pydantic import BaseModel, HttpUrl
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal
from app.db.repositories import TenantRepository, ImageRepository, JobRepository
from app.models.job import JobType

logger = logging.getLogger(__name__)


class ImageManifest(BaseModel):
    """Manifest entry for a seed image."""

    url: str
    filename: str
    source_provider: str
    source_url: str
    license: str
    expected_category: str


def compute_sha256(data: bytes) -> str:
    """Compute SHA256 hex digest of image bytes."""
    return hashlib.sha256(data).hexdigest()


async def download_image(client: httpx.AsyncClient, url: str) -> bytes:
    """Download image bytes from URL with timeout and error handling."""
    try:
        response = await client.get(url, follow_redirects=True, timeout=10.0)
        response.raise_for_status()
        return response.content
    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP error downloading {url}: {e.response.status_code}")
        raise
    except httpx.TimeoutException:
        logger.error(f"Timeout downloading {url}")
        raise
    except Exception as e:
        logger.error(f"Error downloading {url}: {e}")
        raise


class SeedScript:
    """Script to manage downloading seed dataset and seeding database."""

    def __init__(
        self,
        manifest_path: str = "scripts/manifest.json",
        download_dir: str = "data/seed_images",
        tenant_name: str = "demo-tenant",
    ):
        self.manifest_path = manifest_path
        self.download_dir = download_dir
        self.tenant_name = tenant_name

    def load_manifest(self) -> List[Dict[str, Any]]:
        """Load manifest from JSON file."""
        if not os.path.exists(self.manifest_path):
            raise FileNotFoundError(f"Manifest file not found: {self.manifest_path}")
        with open(self.manifest_path, "r", encoding="utf-8") as f:
            return json.load(f)

    async def run(self, session: Optional[AsyncSession] = None) -> dict:
        """Run the seed process.

        Downloads images, calculates SHA256, creates Image records in DB,
        and triggers a batch processing job.
        """
        manifest_entries = self.load_manifest()
        os.makedirs(self.download_dir, exist_ok=True)

        close_session = False
        if session is None:
            session = AsyncSessionLocal()
            close_session = True

        try:
            tenant_repo = TenantRepository(session)
            image_repo = ImageRepository(session)
            job_repo = JobRepository(session)

            tenant = await tenant_repo.get_or_create(self.tenant_name)
            created_images = []
            image_urls = []

            async with httpx.AsyncClient() as client:
                for entry in manifest_entries:
                    url = entry["url"]
                    # Check idempotency by URL or SHA256 beforehand if existing
                    existing = await image_repo.get_by_url(url, tenant.id)
                    if existing:
                        logger.info(f"Image URL already exists: {url}")
                        created_images.append(existing)
                        image_urls.append(url)
                        continue

                    try:
                        content = await download_image(client, url)
                        sha256_hash = compute_sha256(content)

                        # Check idempotency by SHA256
                        existing_hash = await image_repo.get_by_sha256(sha256_hash, tenant.id)
                        if existing_hash:
                            logger.info(f"Image SHA256 already exists: {sha256_hash}")
                            created_images.append(existing_hash)
                            image_urls.append(url)
                            continue

                        # Save local file
                        filepath = os.path.join(self.download_dir, entry["filename"])
                        with open(filepath, "wb") as f:
                            f.write(content)

                        # Create DB record
                        image = await image_repo.create(
                            tenant_id=tenant.id,
                            url=url,
                            filename=entry["filename"],
                            sha256=sha256_hash,
                            source_provider=entry["source_provider"],
                            source_url=entry["source_url"],
                            license=entry["license"],
                            expected_category=entry["expected_category"],
                        )
                        created_images.append(image)
                        image_urls.append(url)
                    except Exception as e:
                        logger.warning(f"Skipping failed download for {url}: {e}")

            # Trigger batch ingestion job
            job = None
            if image_urls:
                job = await job_repo.create(
                    tenant_id=tenant.id,
                    job_type=JobType.IMAGE_INGESTION,
                    payload={"urls": image_urls},
                    idempotency_key=f"seed-job-{uuid.uuid4()}",
                )

            await session.commit()
            return {
                "tenant_id": str(tenant.id),
                "images_processed": len(created_images),
                "job_id": str(job.id) if job else None,
            }
        except Exception as e:
            await session.rollback()
            raise e
        finally:
            if close_session:
                await session.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    script = SeedScript()
    asyncio.run(script.run())
