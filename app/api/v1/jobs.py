"""API endpoints for Background Batch Job Status."""

import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.db.repositories import TenantRepository, JobRepository
from app.schemas.api import JobResponse

router = APIRouter(prefix="/jobs", tags=["Jobs"])


async def get_tenant(session: AsyncSession = Depends(get_db)):
    tenant_repo = TenantRepository(session)
    return await tenant_repo.get_or_create("demo-tenant")


@router.get("/{job_id}", response_model=JobResponse)
async def get_job_status(
    job_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
    tenant=Depends(get_tenant),
):
    """Get background batch processing job status and progress."""
    job_repo = JobRepository(session)
    job = await job_repo.get_by_id(job_id, tenant.id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job {job_id} not found",
        )

    return JobResponse(
        id=job.id,
        tenant_id=job.tenant_id,
        type=job.type,
        status=job.status,
        progress=job.progress,
        payload=job.payload or {},
        error=job.error,
        created_at=job.created_at.isoformat(),
    )
