"""API endpoints for Image Ingestion and Management."""

import uuid
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.db.repositories import TenantRepository, ImageRepository, JobRepository
from app.services.batch_processor import BatchProcessor
from app.schemas.api import ImageIngestRequest, ImageListResponse, ImageResponse, ImageMetadataResponse
from app.models.job import JobType

router = APIRouter(prefix="/images", tags=["Images"])


async def get_tenant(session: AsyncSession = Depends(get_db)):
    tenant_repo = TenantRepository(session)
    return await tenant_repo.get_or_create("demo-tenant")


@router.post("/ingest", status_code=status.HTTP_202_ACCEPTED)
async def ingest_images(
    payload: ImageIngestRequest,
    session: AsyncSession = Depends(get_db),
    tenant=Depends(get_tenant),
):
    """Ingest image URLs and enqueue a background batch processing job."""
    urls = [str(u) for u in payload.urls]
    job_repo = JobRepository(session)

    job = await job_repo.create(
        tenant_id=tenant.id,
        job_type=JobType.IMAGE_INGESTION,
        payload={"urls": urls},
    )

    processor = BatchProcessor(session=session)
    await processor.process_job(job.id, tenant.id)

    return {
        "job_id": str(job.id),
        "status": job.status,
        "total_urls": len(urls),
    }


@router.get("", response_model=ImageListResponse)
async def list_images(
    status_filter: Optional[str] = Query(None, alias="status"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_db),
    tenant=Depends(get_tenant),
):
    """Get paginated list of ingested images with optional status filtering."""
    image_repo = ImageRepository(session)
    images, total = await image_repo.list_images(
        tenant_id=tenant.id,
        status=status_filter,
        limit=limit,
        offset=offset,
    )

    items = []
    for img in images:
        meta_res = None
        if img.img_metadata:
            m = img.img_metadata
            meta_res = ImageMetadataResponse(
                subject=m.subject,
                category=m.category,
                attributes=m.attributes,
                caption=m.caption,
                confidence=m.confidence,
                vision_model=m.vision_model,
                is_low_confidence=m.is_low_confidence,
            )

        items.append(
            ImageResponse(
                id=img.id,
                tenant_id=img.tenant_id,
                url=img.url,
                filename=img.filename,
                sha256=img.sha256,
                source_provider=img.source_provider,
                source_url=img.source_url,
                license=img.license,
                expected_category=img.expected_category,
                status=img.status,
                img_metadata=meta_res,
                created_at=img.created_at.isoformat(),
            )
        )

    return ImageListResponse(
        items=items,
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/{image_id}", response_model=ImageResponse)
async def get_image(
    image_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
    tenant=Depends(get_tenant),
):
    """Get detailed image record by ID."""
    image_repo = ImageRepository(session)
    img = await image_repo.get_by_id(image_id, tenant.id)
    if not img:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Image {image_id} not found",
        )

    meta_res = None
    if img.img_metadata:
        m = img.img_metadata
        meta_res = ImageMetadataResponse(
            subject=m.subject,
            category=m.category,
            attributes=m.attributes,
            caption=m.caption,
            confidence=m.confidence,
            vision_model=m.vision_model,
            is_low_confidence=m.is_low_confidence,
        )

    return ImageResponse(
        id=img.id,
        tenant_id=img.tenant_id,
        url=img.url,
        filename=img.filename,
        sha256=img.sha256,
        source_provider=img.source_provider,
        source_url=img.source_url,
        license=img.license,
        expected_category=img.expected_category,
        status=img.status,
        img_metadata=meta_res,
        created_at=img.created_at.isoformat(),
    )
