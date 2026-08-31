"""Semantic matching engine for matching blog posts to candidate images."""

import math
import uuid
import logging
from typing import List, Optional, Tuple, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.repositories import (
    PostRepository,
    ImageRepository,
    EmbeddingRepository,
    SuggestionRepository,
)
from app.services.embedding import EmbeddingService
from app.services.guard import MismatchGuard, GuardResult
from app.models import Post, Image, Suggestion, Embedding

logger = logging.getLogger(__name__)


def cosine_similarity(vec1: List[float], vec2: List[float]) -> float:
    """Compute cosine similarity between two vector lists."""
    if not vec1 or not vec2 or len(vec1) != len(vec2):
        return 0.0
    dot_product = sum(a * b for a, b in zip(vec1, vec2))
    norm_a = math.sqrt(sum(a * a for a in vec1))
    norm_b = math.sqrt(sum(b * b for b in vec2))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return float(dot_product / (norm_a * norm_b))


class MatchingService:
    """Matching engine service combining vector similarity and mismatch guard."""

    def __init__(
        self,
        session: AsyncSession,
        embedding_service: Optional[EmbeddingService] = None,
        guard: Optional[MismatchGuard] = None,
    ):
        self.session = session
        self.embedding_service = embedding_service or EmbeddingService()
        self.guard = guard or MismatchGuard()
        self.post_repo = PostRepository(session)
        self.image_repo = ImageRepository(session)
        self.embedding_repo = EmbeddingRepository(session)
        self.suggestion_repo = SuggestionRepository(session)

    async def match_post_to_images(
        self,
        post_id: uuid.UUID,
        tenant_id: uuid.UUID,
    ) -> Dict[str, Any]:
        """Match a blog post to candidate images, returning ranked suggestions and guard evaluation."""
        post = await self.post_repo.get_by_id(post_id, tenant_id)
        if not post:
            raise ValueError(f"Post {post_id} not found for tenant {tenant_id}")

        # 1. Get or generate post embedding
        post_embedding_rec = await self.embedding_repo.get_by_source("post_text", post.id)
        if not post_embedding_rec:
            text = f"{post.title}. {post.content}"
            vector = await self.embedding_service.generate_embedding(text)
            post_embedding_rec = await self.embedding_repo.create(
                tenant_id=tenant_id,
                source_type="post_text",
                source_id=post.id,
                vector=vector,
            )
            await self.post_repo.update_embedding_id(post.id, post_embedding_rec.id)

        post_vector = post_embedding_rec.vector

        # 2. Get all image embeddings for tenant
        image_embeddings = await self.embedding_repo.list_image_embeddings(tenant_id)
        if not image_embeddings:
            return {
                "post_id": str(post.id),
                "decision": "no_confident_match",
                "reasons": ["no_images_available"],
                "explanation": "No image embeddings available in repository.",
                "top_suggestion": None,
                "suggestions": [],
            }

        # 3. Compute similarity & run mismatch guard for each image candidate
        candidates = []
        for img_emb in image_embeddings:
            image = await self.image_repo.get_by_id(img_emb.source_id, tenant_id)
            if not image or not image.img_metadata:
                continue

            metadata = image.img_metadata
            sim = cosine_similarity(post_vector, img_emb.vector)

            guard_result = self.guard.evaluate(
                similarity=sim,
                image_category=metadata.category,
                image_confidence=metadata.confidence,
                is_low_confidence=metadata.is_low_confidence,
                expected_category=post.expected_category,
            )

            candidates.append({
                "image": image,
                "metadata": metadata,
                "similarity": sim,
                "guard_result": guard_result,
            })

        if not candidates:
            return {
                "post_id": str(post.id),
                "decision": "no_confident_match",
                "reasons": ["no_valid_candidates"],
                "explanation": "No valid image candidates with metadata found.",
                "top_suggestion": None,
                "suggestions": [],
            }

        # Sort candidates by similarity descending
        candidates.sort(key=lambda c: c["similarity"], reverse=True)

        # 4. Save suggestions and rank
        suggestions = []
        accepted_candidate = None

        for rank_idx, cand in enumerate(candidates, start=1):
            g_res: GuardResult = cand["guard_result"]
            sug = await self.suggestion_repo.create(
                post_id=post.id,
                image_id=cand["image"].id,
                similarity=cand["similarity"],
                guard_decision=g_res.decision,
                guard_reasons=g_res.reasons,
                guard_explanation=g_res.explanation,
                vision_confidence=cand["metadata"].confidence,
                rank=rank_idx,
            )
            suggestions.append(sug)

            if g_res.decision == "accepted" and accepted_candidate is None:
                accepted_candidate = cand

        # 5. Return decision summary
        if accepted_candidate:
            top_g: GuardResult = accepted_candidate["guard_result"]
            return {
                "post_id": str(post.id),
                "decision": "accepted",
                "reasons": top_g.reasons,
                "explanation": top_g.explanation,
                "top_suggestion": {
                    "image_id": str(accepted_candidate["image"].id),
                    "filename": accepted_candidate["image"].filename,
                    "similarity": accepted_candidate["similarity"],
                    "category": accepted_candidate["metadata"].category,
                    "confidence": accepted_candidate["metadata"].confidence,
                },
                "total_candidates": len(candidates),
            }
        else:
            top_cand = candidates[0]
            top_g: GuardResult = top_cand["guard_result"]
            return {
                "post_id": str(post.id),
                "decision": "no_confident_match",
                "reasons": ["no_confident_match"] + top_g.reasons,
                "explanation": f"No candidate passed mismatch guard. Top candidate rejected: {top_g.explanation}",
                "top_suggestion": {
                    "image_id": str(top_cand["image"].id),
                    "filename": top_cand["image"].filename,
                    "similarity": top_cand["similarity"],
                    "category": top_cand["metadata"].category,
                    "confidence": top_cand["metadata"].confidence,
                    "rejected_reasons": top_g.reasons,
                },
                "total_candidates": len(candidates),
            }
