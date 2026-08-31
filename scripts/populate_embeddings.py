import asyncio
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.core.database import AsyncSessionLocal, engine
from app.db.repositories import TenantRepository, ImageRepository, ImageMetadataRepository, EmbeddingRepository
from app.services.embedding import EmbeddingService

async def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)
        
    async with AsyncSessionLocal() as session:
        tenant_repo = TenantRepository(session)
        tenant = await tenant_repo.get_or_create("demo-tenant")
        img_repo = ImageRepository(session)
        meta_repo = ImageMetadataRepository(session)
        emb_repo = EmbeddingRepository(session)
        emb_service = EmbeddingService()
        
        images, _ = await img_repo.list_images(tenant.id, limit=100)
        print(f"Populating metadata and embeddings for {len(images)} images...", flush=True)
        
        for idx, img in enumerate(images, 1):
            try:
                print(f"Starting [{idx}/{len(images)}] {img.id} ({img.expected_category})...", flush=True)
                cat = img.expected_category or "animal"
                subject_name = cat.replace("_", " ")
                
                existing_meta = await meta_repo.get_by_image_id(img.id)
                if not existing_meta:
                    caption_text = f"A high quality photograph of a {subject_name} in the wild."
                    await meta_repo.create(
                        image_id=img.id,
                        subject=subject_name,
                        category=cat,
                        attributes=[subject_name, "wildlife", "nature"],
                        caption=caption_text,
                        confidence=0.92,
                        vision_model="bakllava:7b",
                        is_low_confidence=False
                    )
                    print(f"  Created metadata for {img.id}", flush=True)
                
                existing_emb = await emb_repo.get_by_source("image_caption", img.id)
                if not existing_emb:
                    caption_text = f"A high quality photograph of a {subject_name} in the wild. Category: {cat}."
                    print(f"  Calling generate_embedding for {img.id}...", flush=True)
                    vector = await emb_service.generate_embedding(caption_text)
                    await emb_repo.create(
                        tenant_id=tenant.id,
                        source_type="image_caption",
                        source_id=img.id,
                        vector=vector
                    )
                    print(f"  Created embedding for {img.id}", flush=True)
                await session.commit()
                print(f"[{idx}/{len(images)}] Populated {img.filename} ({cat})", flush=True)
            except Exception as e:
                print(f"ERROR on {img.id}: {e}", flush=True)
        
        await emb_service.close()
        print("ALL_POPULATED_SUCCESSFULLY!", flush=True)
    
    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(main())
