"""Cost tracking service with budget guard."""

import uuid
import logging
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.repositories import CostRepository

logger = logging.getLogger(__name__)


class BudgetExceededError(Exception):
    """Exception raised when budget limit would be exceeded."""
    pass


class CostService:
    """Service for tracking AI operation costs and enforcing budget limits."""

    # Local model costs (USD) - $0 for Ollama local models
    MODEL_COSTS = {
        "bakllava:7b": {"input_per_1k": 0.0, "output_per_1k": 0.0},
        "nomic-embed-text": {"input_per_1k": 0.0, "output_per_1k": 0.0},
    }

    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = CostRepository(session)
        self.max_budget_usd = settings.max_budget_usd
        self._spent_this_session = 0.0

    async def check_budget(self, estimated_cost: float) -> None:
        """Check if adding estimated_cost would exceed budget."""
        if self.max_budget_usd <= 0:
            # No budget limit configured (local models)
            return

        total_spent = await self.get_total_spent()
        if total_spent + estimated_cost > self.max_budget_usd:
            raise BudgetExceededError(
                f"Budget exceeded: current=${total_spent:.6f}, estimated=${estimated_cost:.6f}, "
                f"limit=${self.max_budget_usd:.6f}"
            )

    async def get_total_spent(self) -> float:
        """Get total spent for current tenant."""
        _, _, total = await self.repo.list_costs(
            tenant_id=uuid.UUID(settings.tenant_id) if settings.tenant_id != "demo-tenant" else uuid.UUID("00000000-0000-0000-0000-000000000000"),
            limit=1,
        )
        return total

    def estimate_vision_cost(self, input_tokens: int, output_tokens: int) -> float:
        """Estimate cost for vision model call."""
        model_costs = self.MODEL_COSTS.get(settings.vision_model, {"input_per_1k": 0.0, "output_per_1k": 0.0})
        input_cost = (input_tokens / 1000) * model_costs["input_per_1k"]
        output_cost = (output_tokens / 1000) * model_costs["output_per_1k"]
        return input_cost + output_cost

    def estimate_embedding_cost(self, input_tokens: int) -> float:
        """Estimate cost for embedding model call."""
        model_costs = self.MODEL_COSTS.get(settings.embedding_model, {"input_per_1k": 0.0, "output_per_1k": 0.0})
        return (input_tokens / 1000) * model_costs["input_per_1k"]

    async def record_vision_cost(
        self,
        tenant_id: uuid.UUID,
        related_type: str,
        related_id: uuid.UUID,
        input_tokens: int,
        output_tokens: int,
        status: str = "success",
    ) -> float:
        """Record cost for vision classification call."""
        cost_usd = self.estimate_vision_cost(input_tokens, output_tokens)

        await self.check_budget(cost_usd)

        await self.repo.create(
            tenant_id=tenant_id,
            operation="vision_classification",
            model=settings.vision_model,
            related_type=related_type,
            related_id=related_id,
            tokens_input=input_tokens,
            tokens_output=output_tokens,
            cost_usd=cost_usd,
            status=status,
        )

        logger.info(f"Recorded vision cost: ${cost_usd:.6f} (tokens: {input_tokens} in, {output_tokens} out)")
        return cost_usd

    async def record_embedding_cost(
        self,
        tenant_id: uuid.UUID,
        related_type: str,
        related_id: uuid.UUID,
        input_tokens: int,
        status: str = "success",
    ) -> float:
        """Record cost for embedding generation call."""
        cost_usd = self.estimate_embedding_cost(input_tokens)

        await self.check_budget(cost_usd)

        await self.repo.create(
            tenant_id=tenant_id,
            operation="embedding_generation",
            model=settings.embedding_model,
            related_type=related_type,
            related_id=related_id,
            tokens_input=input_tokens,
            tokens_output=0,
            cost_usd=cost_usd,
            status=status,
        )

        logger.info(f"Recorded embedding cost: ${cost_usd:.6f} (tokens: {input_tokens} in)")
        return cost_usd

    async def record_failed_cost(
        self,
        tenant_id: uuid.UUID,
        operation: str,
        model: str,
        related_type: Optional[str] = None,
        related_id: Optional[uuid.UUID] = None,
    ) -> None:
        """Record a failed AI call with $0 cost."""
        await self.repo.create(
            tenant_id=tenant_id,
            operation=operation,
            model=model,
            related_type=related_type,
            related_id=related_id,
            tokens_input=0,
            tokens_output=0,
            cost_usd=0.0,
            status="failed",
        )
        logger.warning(f"Recorded failed {operation} call for {model}")