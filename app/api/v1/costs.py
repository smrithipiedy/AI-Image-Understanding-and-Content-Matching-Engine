"""API endpoints for Per-Call Cost Tracking."""

from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.db.repositories import TenantRepository, CostRepository
from app.schemas.api import CostListResponse, CostRecordResponse

router = APIRouter(prefix="/costs", tags=["Cost Log"])


async def get_tenant(session: AsyncSession = Depends(get_db)):
    tenant_repo = TenantRepository(session)
    return await tenant_repo.get_or_create("demo-tenant")


@router.get("", response_model=CostListResponse)
async def list_costs(
    operation: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_db),
    tenant=Depends(get_tenant),
):
    """Get paginated AI usage cost logs with operation filtering and total sum."""
    cost_repo = CostRepository(session)
    costs, total, total_cost_usd = await cost_repo.list_costs(
        tenant_id=tenant.id,
        operation=operation,
        limit=limit,
        offset=offset,
    )

    items = [
        CostRecordResponse(
            id=c.id,
            tenant_id=c.tenant_id,
            operation=c.operation,
            model=c.model,
            related_type=c.related_type,
            related_id=c.related_id,
            tokens_input=c.tokens_input,
            tokens_output=c.tokens_output,
            cost_usd=c.cost_usd,
            status=c.status,
            created_at=c.created_at.isoformat(),
        )
        for c in costs
    ]

    return CostListResponse(
        items=items,
        total=total,
        total_cost_usd=total_cost_usd,
        limit=limit,
        offset=offset,
    )
