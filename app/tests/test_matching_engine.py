"""Tests for MatchingService semantic matching engine."""

import pytest
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.matching import MatchingService, cosine_similarity


class TestCosineSimilarity:
    """Tests for cosine similarity vector function."""

    def test_identical_vectors(self):
        v = [1.0, 0.0, 0.0]
        assert cosine_similarity(v, v) == 1.0

    def test_orthogonal_vectors(self):
        v1 = [1.0, 0.0]
        v2 = [0.0, 1.0]
        assert cosine_similarity(v1, v2) == 0.0

    def test_opposite_vectors(self):
        v1 = [1.0, 1.0]
        v2 = [-1.0, -1.0]
        assert pytest.approx(cosine_similarity(v1, v2)) == -1.0


class TestMatchingService:
    """Tests for MatchingService pipeline."""

    @pytest.mark.asyncio
    async def test_match_post_finds_top_fox_image(self):
        """Probe 2 requirement: Fox post should rank fox image first."""
        mock_session = AsyncMock()
        mock_embedding_service = AsyncMock()

        processor = MatchingService(session=mock_session, embedding_service=mock_embedding_service)

        tenant_id = uuid.uuid4()
        post_id = uuid.uuid4()
        fox_image_id = uuid.uuid4()
        wolf_image_id = uuid.uuid4()

        mock_post = MagicMock()
        mock_post.id = post_id
        mock_post.title = "Red Fox in the Woods"
        mock_post.content = "A story about a red fox."
        mock_post.expected_category = "red_fox"

        processor.post_repo.get_by_id = AsyncMock(return_value=mock_post)
        processor.post_repo.update_embedding_id = AsyncMock()

        fox_emb = MagicMock()
        fox_emb.source_id = fox_image_id
        fox_emb.vector = [1.0, 0.0, 0.0]

        wolf_emb = MagicMock()
        wolf_emb.source_id = wolf_image_id
        wolf_emb.vector = [0.0, 1.0, 0.0]

        post_emb = MagicMock()
        post_emb.vector = [1.0, 0.0, 0.0]

        processor.embedding_repo.get_by_source = AsyncMock(return_value=post_emb)
        processor.embedding_repo.list_image_embeddings = AsyncMock(return_value=[fox_emb, wolf_emb])

        fox_img = MagicMock()
        fox_img.id = fox_image_id
        fox_img.filename = "fox1.jpg"
        fox_img.img_metadata = MagicMock(category="red_fox", confidence=0.95, is_low_confidence=False)

        wolf_img = MagicMock()
        wolf_img.id = wolf_image_id
        wolf_img.filename = "wolf1.jpg"
        wolf_img.img_metadata = MagicMock(category="wolf", confidence=0.90, is_low_confidence=False)

        async def mock_get_image_by_id(img_id, t_id):
            if img_id == fox_image_id:
                return fox_img
            return wolf_img

        processor.image_repo.get_by_id = AsyncMock(side_effect=mock_get_image_by_id)
        processor.suggestion_repo.create = AsyncMock()

        result = await processor.match_post_to_images(post_id, tenant_id)

        assert result["decision"] == "accepted"
        assert result["top_suggestion"]["image_id"] == str(fox_image_id)
        assert result["top_suggestion"]["filename"] == "fox1.jpg"

    @pytest.mark.asyncio
    async def test_match_post_no_confident_match(self):
        """Probe 4 requirement: Post with no matching candidates should return no_confident_match."""
        mock_session = AsyncMock()
        mock_embedding_service = AsyncMock()

        processor = MatchingService(session=mock_session, embedding_service=mock_embedding_service)

        tenant_id = uuid.uuid4()
        post_id = uuid.uuid4()
        wolf_image_id = uuid.uuid4()

        mock_post = MagicMock()
        mock_post.id = post_id
        mock_post.title = "Red Fox Post"
        mock_post.content = "Searching for fox."
        mock_post.expected_category = "red_fox"

        processor.post_repo.get_by_id = AsyncMock(return_value=mock_post)
        processor.post_repo.update_embedding_id = AsyncMock()

        # Only wolf image available (category mismatch)
        wolf_emb = MagicMock()
        wolf_emb.source_id = wolf_image_id
        wolf_emb.vector = [1.0, 0.0, 0.0]

        post_emb = MagicMock()
        post_emb.vector = [1.0, 0.0, 0.0]

        processor.embedding_repo.get_by_source = AsyncMock(return_value=post_emb)
        processor.embedding_repo.list_image_embeddings = AsyncMock(return_value=[wolf_emb])

        wolf_img = MagicMock()
        wolf_img.id = wolf_image_id
        wolf_img.filename = "wolf1.jpg"
        wolf_img.img_metadata = MagicMock(category="wolf", confidence=0.90, is_low_confidence=False)

        processor.image_repo.get_by_id = AsyncMock(return_value=wolf_img)
        processor.suggestion_repo.create = AsyncMock()

        result = await processor.match_post_to_images(post_id, tenant_id)

        assert result["decision"] == "no_confident_match"
        assert "no_confident_match" in result["reasons"]
