"""Database repositories for data access."""

import uuid
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import select, func, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import Tenant, Image, ImageMetadata, ImageStatus, Job, JobStatus, Cost, Embedding, Post, Suggestion, Approval


class TenantRepository:
    """Repository for tenant operations."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_name(self, name: str) -> Optional[Tenant]:
        result = await self.session.execute(select(Tenant).where(Tenant.name == name))
        return result.scalar_one_or_none()

    async def get_or_create(self, name: str) -> Tenant:
        tenant = await self.get_by_name(name)
        if tenant:
            return tenant
        tenant = Tenant(id=uuid.uuid4(), name=name)
        self.session.add(tenant)
        await self.session.flush()
        return tenant


class ImageRepository:
    """Repository for image operations."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(self, image_id: uuid.UUID, tenant_id: uuid.UUID) -> Optional[Image]:
        result = await self.session.execute(
            select(Image)
            .options(selectinload(Image.img_metadata))
            .where(Image.id == image_id, Image.tenant_id == tenant_id)
        )
        return result.scalar_one_or_none()

    async def get_by_sha256(self, sha256: str, tenant_id: uuid.UUID) -> Optional[Image]:
        result = await self.session.execute(
            select(Image)
            .where(Image.sha256 == sha256, Image.tenant_id == tenant_id)
        )
        return result.scalar_one_or_none()

    async def get_by_url(self, url: str, tenant_id: uuid.UUID) -> Optional[Image]:
        result = await self.session.execute(
            select(Image)
            .where(Image.url == url, Image.tenant_id == tenant_id)
        )
        return result.scalar_one_or_none()

    async def create(
        self,
        tenant_id: uuid.UUID,
        url: str,
        filename: str,
        sha256: str,
        source_provider: str,
        source_url: str,
        license: str,
        expected_category: Optional[str] = None,
    ) -> Image:
        image = Image(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            url=url,
            filename=filename,
            sha256=sha256,
            source_provider=source_provider,
            source_url=source_url,
            license=license,
            expected_category=expected_category,
            status=ImageStatus.PENDING,
        )
        self.session.add(image)
        await self.session.flush()
        return image

    async def update_status(self, image_id: uuid.UUID, status: str) -> None:
        await self.session.execute(
            update(Image)
            .where(Image.id == image_id)
            .values(status=status, updated_at=func.now())
        )

    async def list_images(
        self,
        tenant_id: uuid.UUID,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[Image], int]:
        query = select(Image).where(Image.tenant_id == tenant_id)
        if status:
            query = query.where(Image.status == status)

        # Get total count
        count_query = select(func.count()).select_from(query.subquery())
        count_res = await self.session.execute(count_query)
        total = count_res.scalar() or 0

        # Get paginated results
        query = query.order_by(Image.created_at.desc()).limit(limit).offset(offset)
        result = await self.session.execute(query)
        images = result.scalars().all()

        return list(images), total


class ImageMetadataRepository:
    """Repository for image metadata operations."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(
        self,
        image_id: uuid.UUID,
        subject: str,
        category: str,
        attributes: list[str],
        caption: str,
        confidence: float,
        vision_model: str,
        is_low_confidence: bool,
    ) -> ImageMetadata:
        metadata = ImageMetadata(
            id=uuid.uuid4(),
            image_id=image_id,
            subject=subject,
            category=category,
            attributes=attributes,
            caption=caption,
            confidence=confidence,
            vision_model=vision_model,
            is_low_confidence=is_low_confidence,
            validated_at=datetime.now(timezone.utc),
        )
        self.session.add(metadata)
        await self.session.flush()
        return metadata

    async def get_by_image_id(self, image_id: uuid.UUID) -> Optional[ImageMetadata]:
        result = await self.session.execute(
            select(ImageMetadata).where(ImageMetadata.image_id == image_id)
        )
        return result.scalar_one_or_none()


class JobRepository:
    """Repository for job operations."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(self, job_id: uuid.UUID, tenant_id: uuid.UUID) -> Optional[Job]:
        result = await self.session.execute(
            select(Job).where(Job.id == job_id, Job.tenant_id == tenant_id)
        )
        return result.scalar_one_or_none()

    async def get_by_idempotency_key(self, key: str) -> Optional[Job]:
        result = await self.session.execute(
            select(Job).where(Job.idempotency_key == key)
        )
        return result.scalar_one_or_none()

    async def create(
        self,
        tenant_id: uuid.UUID,
        job_type: str,
        payload: dict,
        idempotency_key: Optional[str] = None,
    ) -> Job:
        job = Job(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            type=job_type,
            payload=payload,
            idempotency_key=idempotency_key,
            status=JobStatus.PENDING,
            progress=0,
        )
        self.session.add(job)
        await self.session.flush()
        return job

    async def update_status(
        self,
        job_id: uuid.UUID,
        status: str,
        progress: Optional[int] = None,
        error: Optional[str] = None,
    ) -> None:
        values = {"status": status}
        if progress is not None:
            values["progress"] = progress
        if error is not None:
            values["error"] = error
        if status == JobStatus.PROCESSING:
            values["started_at"] = func.now()
        elif status in (JobStatus.COMPLETED, JobStatus.FAILED):
            values["completed_at"] = func.now()

        await self.session.execute(
            update(Job).where(Job.id == job_id).values(**values)
        )


class CostRepository:
    """Repository for cost tracking operations."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(
        self,
        tenant_id: uuid.UUID,
        operation: str,
        model: str,
        related_type: Optional[str] = None,
        related_id: Optional[uuid.UUID] = None,
        tokens_input: Optional[int] = None,
        tokens_output: Optional[int] = None,
        cost_usd: float = 0.0,
        status: str = "success",
    ) -> Cost:
        cost = Cost(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            operation=operation,
            model=model,
            related_type=related_type,
            related_id=related_id,
            tokens_input=tokens_input,
            tokens_output=tokens_output,
            cost_usd=cost_usd,
            status=status,
        )
        self.session.add(cost)
        await self.session.flush()
        return cost

    async def list_costs(
        self,
        tenant_id: uuid.UUID,
        operation: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[Cost], int, float]:
        query = select(Cost).where(Cost.tenant_id == tenant_id)
        if operation:
            query = query.where(Cost.operation == operation)

        # Get total count and sum
        count_query = select(func.count()).select_from(query.subquery())
        count_res = await self.session.execute(count_query)
        total = count_res.scalar() or 0

        sum_query = select(func.coalesce(func.sum(Cost.cost_usd), 0)).where(Cost.tenant_id == tenant_id)
        sum_res = await self.session.execute(sum_query)
        total_cost = sum_res.scalar() or 0.0

        # Get paginated results
        query = query.order_by(Cost.created_at.desc()).limit(limit).offset(offset)
        result = await self.session.execute(query)
        costs = result.scalars().all()

        return list(costs), total, float(total_cost)


class EmbeddingRepository:
    """Repository for vector embedding operations."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(
        self,
        tenant_id: uuid.UUID,
        source_type: str,
        source_id: uuid.UUID,
        vector: list[float],
        model: str = "nomic-embed-text",
    ) -> Embedding:
        embedding = Embedding(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            source_type=source_type,
            source_id=source_id,
            vector=vector,
            model=model,
        )
        self.session.add(embedding)
        await self.session.flush()
        return embedding

    async def get_by_source(self, source_type: str, source_id: uuid.UUID) -> Optional[Embedding]:
        result = await self.session.execute(
            select(Embedding).where(
                Embedding.source_type == source_type,
                Embedding.source_id == source_id,
            )
        )
        return result.scalar_one_or_none()

    async def list_image_embeddings(self, tenant_id: uuid.UUID) -> list[Embedding]:
        result = await self.session.execute(
            select(Embedding).where(
                Embedding.tenant_id == tenant_id,
                Embedding.source_type == "image_caption",
            )
        )
        return list(result.scalars().all())


class PostRepository:
    """Repository for blog post operations."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(
        self,
        tenant_id: uuid.UUID,
        title: str,
        content: str,
        expected_category: Optional[str] = None,
        expected_image_id: Optional[uuid.UUID] = None,
        is_evaluation: bool = False,
    ) -> Post:
        post = Post(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            title=title,
            content=content,
            expected_category=expected_category,
            expected_image_id=expected_image_id,
            is_evaluation=is_evaluation,
        )
        self.session.add(post)
        await self.session.flush()
        return post

    async def get_by_id(self, post_id: uuid.UUID, tenant_id: uuid.UUID) -> Optional[Post]:
        result = await self.session.execute(
            select(Post).where(Post.id == post_id, Post.tenant_id == tenant_id)
        )
        return result.scalar_one_or_none()

    async def update_embedding_id(self, post_id: uuid.UUID, embedding_id: uuid.UUID) -> None:
        await self.session.execute(
            update(Post).where(Post.id == post_id).values(embedding_id=embedding_id)
        )

    async def list_posts(self, tenant_id: uuid.UUID) -> list[Post]:
        result = await self.session.execute(
            select(Post).where(Post.tenant_id == tenant_id)
        )
        return list(result.scalars().all())


class SuggestionRepository:
    """Repository for suggestion match operations."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(
        self,
        post_id: uuid.UUID,
        image_id: uuid.UUID,
        similarity: float,
        guard_decision: str,
        guard_reasons: list[str],
        guard_explanation: Optional[str] = None,
        vision_confidence: Optional[float] = None,
        rank: int = 1,
    ) -> Suggestion:
        suggestion = Suggestion(
            id=uuid.uuid4(),
            post_id=post_id,
            image_id=image_id,
            similarity=similarity,
            guard_decision=guard_decision,
            guard_reasons=guard_reasons,
            guard_explanation=guard_explanation,
            vision_confidence=vision_confidence,
            rank=rank,
        )
        self.session.add(suggestion)
        await self.session.flush()
        return suggestion

    async def list_by_post_id(self, post_id: uuid.UUID) -> list[Suggestion]:
        result = await self.session.execute(
            select(Suggestion).where(Suggestion.post_id == post_id).order_by(Suggestion.rank.asc())
        )
        return list(result.scalars().all())