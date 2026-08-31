"""Tests for cost service - TDD: written BEFORE implementation."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import uuid
from decimal import Decimal

from app.services.cost import CostService, BudgetExceededError
from app.models.cost import Cost
from app.core.config import settings


class TestCostService:
    """Tests for CostService."""

    @pytest.fixture
    def mock_session(self):
        """Create a mock async session."""
        return AsyncMock()

    @pytest.fixture
    def cost_service(self, mock_session):
        """Create a CostService instance with mocked repository."""
        with patch('app.services.cost.CostRepository') as mock_repo_class:
            mock_repo = AsyncMock()
            mock_repo_class.return_value = mock_repo
            service = CostService(mock_session)
            service.repo = mock_repo
            return service

    @pytest.fixture
    def tenant_id(self):
        """Sample tenant ID."""
        return uuid.uuid4()

    @pytest.fixture
    def related_id(self):
        """Sample related entity ID."""
        return uuid.uuid4()

    @pytest.mark.asyncio
    async def test_check_budget_no_limit(self, cost_service):
        """No budget limit (MAX_BUDGET_USD=0) should allow any spending."""
        cost_service.max_budget_usd = 0.0
        # Should not raise
        await cost_service.check_budget(1000.0)
        await cost_service.check_budget(0.0)

    @pytest.mark.asyncio
    async def test_check_budget_within_limit(self, cost_service, mock_session):
        """Budget check should pass when within limit."""
        cost_service.max_budget_usd = 10.0
        cost_service.repo.list_costs.return_value = ([], 0, 5.0)  # $5 spent so far

        await cost_service.check_budget(3.0)  # $5 + $3 = $8 < $10

    @pytest.mark.asyncio
    async def test_check_budget_exceeds_limit(self, cost_service, mock_session):
        """Budget check should raise when limit would be exceeded."""
        cost_service.max_budget_usd = 10.0
        cost_service.repo.list_costs.return_value = ([], 0, 8.0)  # $8 spent so far

        with pytest.raises(BudgetExceededError) as exc_info:
            await cost_service.check_budget(3.0)  # $8 + $3 = $11 > $10

        assert "budget exceeded" in str(exc_info.value).lower()
        assert "10" in str(exc_info.value)  # limit mentioned

    @pytest.mark.asyncio
    async def test_check_budget_at_limit(self, cost_service, mock_session):
        """Budget check should pass when exactly at limit."""
        cost_service.max_budget_usd = 10.0
        cost_service.repo.list_costs.return_value = ([], 0, 7.0)

        await cost_service.check_budget(3.0)  # $7 + $3 = $10 exactly

    @pytest.mark.asyncio
    async def test_record_vision_cost_local_model(self, cost_service, tenant_id, related_id):
        """Vision cost for local model should be $0 but still recorded."""
        cost_service.max_budget_usd = 0.0  # Local model - no cost limit

        cost_usd = await cost_service.record_vision_cost(
            tenant_id=tenant_id,
            related_type="image",
            related_id=related_id,
            input_tokens=100,
            output_tokens=50,
        )

        assert cost_usd == 0.0
        cost_service.repo.create.assert_called_once()
        call_args = cost_service.repo.create.call_args
        assert call_args.kwargs['operation'] == "vision_classification"
        assert call_args.kwargs['model'] == settings.vision_model
        assert call_args.kwargs['tokens_input'] == 100
        assert call_args.kwargs['tokens_output'] == 50
        assert call_args.kwargs['cost_usd'] == 0.0
        assert call_args.kwargs['status'] == "success"

    @pytest.mark.asyncio
    async def test_record_embedding_cost_local_model(self, cost_service, tenant_id, related_id):
        """Embedding cost for local model should be $0 but still recorded."""
        cost_service.max_budget_usd = 0.0

        cost_usd = await cost_service.record_embedding_cost(
            tenant_id=tenant_id,
            related_type="image",
            related_id=related_id,
            input_tokens=200,
        )

        assert cost_usd == 0.0
        cost_service.repo.create.assert_called_once()
        call_args = cost_service.repo.create.call_args
        assert call_args.kwargs['operation'] == "embedding_generation"
        assert call_args.kwargs['model'] == settings.embedding_model
        assert call_args.kwargs['tokens_input'] == 200
        assert call_args.kwargs['tokens_output'] == 0
        assert call_args.kwargs['cost_usd'] == 0.0

    @pytest.mark.asyncio
    async def test_record_vision_cost_checks_budget(self, cost_service, tenant_id, related_id):
        """record_vision_cost should check budget before recording."""
        cost_service.max_budget_usd = 1.0
        cost_service.repo.list_costs.return_value = ([], 0, 0.90)  # $0.90 spent

        # This would exceed budget (0.90 + estimated > 1.0)
        with pytest.raises(BudgetExceededError):
            await cost_service.record_vision_cost(
                tenant_id=tenant_id,
                related_type="image",
                related_id=related_id,
                input_tokens=1000000,  # Large tokens = high estimated cost
                output_tokens=1000000,
            )

    @pytest.mark.asyncio
    async def test_record_failed_cost(self, cost_service, tenant_id, related_id):
        """Failed AI calls should be recorded with $0 cost and failed status."""
        await cost_service.record_failed_cost(
            tenant_id=tenant_id,
            operation="vision_classification",
            model="bakllava:7b",
            related_type="image",
            related_id=related_id,
        )

        cost_service.repo.create.assert_called_once()
        call_args = cost_service.repo.create.call_args
        assert call_args.kwargs['operation'] == "vision_classification"
        assert call_args.kwargs['model'] == "bakllava:7b"
        assert call_args.kwargs['cost_usd'] == 0.0
        assert call_args.kwargs['status'] == "failed"
        assert call_args.kwargs['tokens_input'] == 0
        assert call_args.kwargs['tokens_output'] == 0

    @pytest.mark.asyncio
    async def test_estimate_vision_cost_local(self, cost_service):
        """Vision cost estimation for local model should be $0."""
        cost = cost_service.estimate_vision_cost(1000, 500)
        assert cost == 0.0

    @pytest.mark.asyncio
    async def test_estimate_embedding_cost_local(self, cost_service):
        """Embedding cost estimation for local model should be $0."""
        cost = cost_service.estimate_embedding_cost(1000)
        assert cost == 0.0


class TestBudgetExceededError:
    """Tests for BudgetExceededError."""

    def test_error_message_contains_details(self):
        """Error message should contain relevant details."""
        error = BudgetExceededError(
            "Budget exceeded: current=$5.000000, estimated=$3.000000, limit=$7.000000"
        )
        assert "5.0" in str(error)
        assert "3.0" in str(error)
        assert "7.0" in str(error)
        assert "budget exceeded" in str(error).lower()