"""API endpoints for Human Review of Match Suggestions."""

import uuid
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.db.repositories import TenantRepository, SuggestionRepository
from app.models.suggestion import Suggestion, Approval
from app.schemas.api import ApprovalRequest

router = APIRouter(prefix="/suggestions", tags=["Suggestions Review"])


async def get_tenant(session: AsyncSession = Depends(get_db)):
    tenant_repo = TenantRepository(session)
    return await tenant_repo.get_or_create("demo-tenant")


@router.post("/{suggestion_id}/approval", status_code=status.HTTP_201_CREATED)
async def submit_suggestion_approval(
    suggestion_id: uuid.UUID,
    payload: ApprovalRequest,
    session: AsyncSession = Depends(get_db),
    tenant=Depends(get_tenant),
):
    """Record human reviewer approval or rejection decision for a match suggestion."""
    result = await session.execute(
        select(Suggestion).where(Suggestion.id == suggestion_id)
    )
    suggestion = result.scalar_one_or_none()
    if not suggestion:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Suggestion {suggestion_id} not found",
        )

    approval = Approval(
        id=uuid.uuid4(),
        suggestion_id=suggestion.id,
        decision=payload.decision,
        reviewer_note=payload.reviewer_note,
    )
    session.add(approval)
    await session.flush()

    return {
        "id": str(approval.id),
        "suggestion_id": str(approval.suggestion_id),
        "decision": approval.decision,
        "reviewer_note": approval.reviewer_note,
        "decided_at": approval.decided_at.isoformat(),
    }


@router.get("/{suggestion_id}")
async def get_suggestion_details(
    suggestion_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
    tenant=Depends(get_tenant),
):
    """Inspect suggestion details, mismatch guard reasons, and approval history."""
    result = await session.execute(
        select(Suggestion).where(Suggestion.id == suggestion_id)
    )
    sug = result.scalar_one_or_none()
    if not sug:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Suggestion {suggestion_id} not found",
        )

    appr_res = await session.execute(
        select(Approval).where(Approval.suggestion_id == sug.id)
    )
    approvals = appr_res.scalars().all()

    return {
        "id": str(sug.id),
        "post_id": str(sug.post_id),
        "image_id": str(sug.image_id),
        "similarity": sug.similarity,
        "guard_decision": sug.guard_decision,
        "guard_reasons": sug.guard_reasons,
        "guard_explanation": sug.guard_explanation,
        "vision_confidence": sug.vision_confidence,
        "rank": sug.rank,
        "created_at": sug.created_at.isoformat(),
        "approvals": [
            {
                "id": str(a.id),
                "decision": a.decision,
                "reviewer_note": a.reviewer_note,
                "decided_at": a.decided_at.isoformat(),
            }
            for a in approvals
        ],
    }
