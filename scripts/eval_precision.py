"""Evaluation script to measure Top-1 Precision on a labeled dataset.

PROBE 5 Requirement:
Run evaluation on 10 labeled posts and measure top-1 recommendation precision.
"""

import sys
import os
import asyncio
import logging
from sqlalchemy import select

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.core.database import AsyncSessionLocal
from app.db.repositories import TenantRepository, PostRepository, ImageRepository
from app.services.matching import MatchingService
from app.models.post import Post

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("eval_precision")

EVAL_POSTS_DATA = [
    {"title": "The Behavior of Red Foxes in North America", "content": "Detailed study of Vulpes vulpes hunting in forest habitats and nocturnal behavior.", "expected_category": "red_fox"},
    {"title": "Wild Red Fox Population Dynamics", "content": "Examining orange fur red fox populations and territorial ranges.", "expected_category": "red_fox"},
    {"title": "Gray Wolf Pack Dynamics and Hunting Strategy", "content": "Analysis of Canis lupus wolf packs in snow and forest environments.", "expected_category": "wolf"},
    {"title": "Wolf Communication and Howling Patterns", "content": "Scientific overview of wild gray wolves communicating across northern forests.", "expected_category": "wolf"},
    {"title": "Domestic Dog Breeds and Training Techniques", "content": "Guide to domestic dog behavior, obedience training, and household pets.", "expected_category": "dog"},
    {"title": "Canine Companionship and Care", "content": "Understanding loyal domestic dogs, puppy care, and pet nutrition.", "expected_category": "dog"},
    {"title": "Grizzly Bear Hibernation and Foraging Patterns", "content": "Ursus arctos grizzly bear feeding habits in mountain rivers and streams.", "expected_category": "bear"},
    {"title": "Brown Bear Habitats and Wilderness Conservation", "content": "Tracking large brown bears in national parks and wilderness preserves.", "expected_category": "bear"},
    {"title": "White-Tailed Deer Migration and Grazing", "content": "Observing wild deer species grazing in meadows and woodland clearings.", "expected_category": "deer"},
    {"title": "Deer Antler Growth and Seasonal Foraging", "content": "Study of cervid antler cycles and deer behavior during autumn.", "expected_category": "deer"},
]


async def run_evaluation():
    """Execute evaluation and compute top-1 precision."""
    logger.info("Starting Top-1 Precision Evaluation on labeled dataset...")
    async with AsyncSessionLocal() as session:
        tenant_repo = TenantRepository(session)
        tenant = await tenant_repo.get_or_create("demo-tenant")

        post_repo = PostRepository(session)
        matching_service = MatchingService(session=session)

        # Step 1: Ensure labeled posts exist in database
        eval_posts = []
        for item in EVAL_POSTS_DATA:
            stmt = select(Post).where(
                Post.tenant_id == tenant.id,
                Post.title == item["title"]
            )
            result = await session.execute(stmt)
            existing = result.scalar_one_or_none()

            if existing:
                eval_posts.append(existing)
            else:
                p = await post_repo.create(
                    tenant_id=tenant.id,
                    title=item["title"],
                    content=item["content"],
                    expected_category=item["expected_category"],
                    is_evaluation=True
                )
                eval_posts.append(p)

        logger.info(f"Loaded {len(eval_posts)} labeled posts for evaluation.")

        # Step 2: Run matching engine for each post
        correct_matches = 0
        total_eval = len(eval_posts)

        print("\n=================== EVALUATION RESULTS ===================")
        for idx, post in enumerate(eval_posts, 1):
            match_res = await matching_service.match_post_to_images(post_id=post.id, tenant_id=tenant.id)
            expected = post.expected_category

            if match_res["status"] == "matched" and match_res["match"]:
                matched_image = match_res["match"]
                detected_category = matched_image.get("category") or matched_image.get("expected_category")

                is_correct = (detected_category == expected) or (expected in str(matched_image.get("subject", "")))
                if is_correct:
                    correct_matches += 1
                    symbol = "✔ [PASS]"
                else:
                    symbol = "✘ [FAIL]"

                print(f"Post {idx:02d}: '{post.title[:45]}...'")
                print(f"   Expected Category: {expected}")
                print(f"   Matched Image Subject: {matched_image.get('subject')} (Category: {detected_category})")
                print(f"   Similarity: {match_res['match'].get('similarity', 0.0):.4f} | Result: {symbol}\n")
            else:
                print(f"Post {idx:02d}: '{post.title[:45]}...'")
                print(f"   Expected Category: {expected}")
                print(f"   Result: ✘ [NO MATCH] ({match_res.get('explanation')})\n")

        precision = (correct_matches / total_eval) * 100.0 if total_eval > 0 else 0.0

        print("=================== SUMMARY METRICS ===================")
        print(f"Total Evaluated Posts : {total_eval}")
        print(f"Correct Top-1 Matches : {correct_matches}")
        print(f"Top-1 Precision Score : {precision:.1f}%")
        print("=======================================================\n")

        return precision


if __name__ == "__main__":
    asyncio.run(run_evaluation())
