"""API endpoints for Blog Posts and Image Matching."""

import uuid
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.db.repositories import TenantRepository, PostRepository
from app.services.matching import MatchingService
from app.schemas.api import PostCreateRequest

router = APIRouter(prefix="/posts", tags=["Posts"])


async def get_tenant(session: AsyncSession = Depends(get_db)):
    tenant_repo = TenantRepository(session)
    return await tenant_repo.get_or_create("demo-tenant")


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_post(
    payload: PostCreateRequest,
    session: AsyncSession = Depends(get_db),
    tenant=Depends(get_tenant),
):
    """Create a blog post and generate its text embedding."""
    post_repo = PostRepository(session)
    post = await post_repo.create(
        tenant_id=tenant.id,
        title=payload.title,
        content=payload.content,
        expected_category=payload.expected_category,
        is_evaluation=payload.is_evaluation,
    )
    return {
        "id": str(post.id),
        "title": post.title,
        "expected_category": post.expected_category,
        "created_at": post.created_at.isoformat(),
    }


@router.get("/{post_id}/matches")
async def get_post_image_matches(
    post_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
    tenant=Depends(get_tenant),
):
    """Query image suggestions for a blog post via semantic search and mismatch guard."""
    post_repo = PostRepository(session)
    post = await post_repo.get_by_id(post_id, tenant.id)
    if not post:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Post {post_id} not found",
        )

    matching_service = MatchingService(session=session)
    result = await matching_service.match_post_to_images(post_id=post.id, tenant_id=tenant.id)
    return result
