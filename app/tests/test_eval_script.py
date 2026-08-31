"""Tests for the evaluation precision script (PROBE 5)."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from scripts.eval_precision import run_evaluation


@pytest.mark.asyncio
async def test_eval_precision_script_calculation():
    """Verify that evaluation script calculates top-1 precision correctly."""
    mock_post = MagicMock()
    mock_post.id = "post-1"
    mock_post.title = "The Behavior of Red Foxes in North America"
    mock_post.expected_category = "red_fox"

    mock_match_result = {
        "status": "matched",
        "match": {
            "subject": "red fox",
            "category": "red_fox",
            "similarity": 0.88,
        },
    }

    with patch("scripts.eval_precision.AsyncSessionLocal") as MockSessionLocal, \
         patch("scripts.eval_precision.TenantRepository") as MockTenantRepo, \
         patch("scripts.eval_precision.PostRepository") as MockPostRepo, \
         patch("scripts.eval_precision.MatchingService") as MockMatchingService:

        mock_session = AsyncMock()
        mock_exec_res = MagicMock()
        mock_exec_res.scalar_one_or_none.return_value = mock_post
        mock_session.execute.return_value = mock_exec_res
        MockSessionLocal.return_value.__aenter__.return_value = mock_session

        tenant_inst = AsyncMock()
        tenant_inst.get_or_create.return_value = MagicMock(id="tenant-1")
        MockTenantRepo.return_value = tenant_inst

        post_inst = AsyncMock()
        post_inst.create = AsyncMock(return_value=mock_post)
        MockPostRepo.return_value = post_inst

        match_inst = AsyncMock()
        match_inst.match_post_to_images = AsyncMock(return_value=mock_match_result)
        MockMatchingService.return_value = match_inst

        precision = await run_evaluation()
        assert precision == 100.0
