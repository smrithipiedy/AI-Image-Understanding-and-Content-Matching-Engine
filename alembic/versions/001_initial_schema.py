"""Initial schema for FlyRank capstone.

Revision ID: 001
Revises:
Create Date: 2026-08-31

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create pgvector extension
    op.execute('CREATE EXTENSION IF NOT EXISTS vector')

    # Tenants table
    op.create_table(
        'tenants',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('name', sa.String(255), nullable=False, unique=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    )

    # Images table
    op.create_table(
        'images',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False),
        sa.Column('url', sa.Text, nullable=False),
        sa.Column('filename', sa.String(255), nullable=False),
        sa.Column('sha256', sa.String(64), nullable=False, unique=True),
        sa.Column('source_provider', sa.String(100), nullable=False),
        sa.Column('source_url', sa.Text, nullable=False),
        sa.Column('license', sa.String(100), nullable=False),
        sa.Column('expected_category', sa.String(100), nullable=True),
        sa.Column('status', sa.String(50), nullable=False, server_default='pending'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    )
    op.create_index('idx_images_tenant', 'images', ['tenant_id'])
    op.create_index('idx_images_status', 'images', ['status'])
    op.create_index('idx_images_sha256', 'images', ['sha256'], unique=True)

    # Image Metadata table
    op.create_table(
        'image_metadata',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('image_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('images.id', ondelete='CASCADE'), nullable=False, unique=True),
        sa.Column('subject', sa.String(255), nullable=False),
        sa.Column('category', sa.String(100), nullable=False),
        sa.Column('attributes', postgresql.JSONB, nullable=False, server_default='[]'),
        sa.Column('caption', sa.Text, nullable=False),
        sa.Column('confidence', sa.Numeric(3, 2), nullable=False),
        sa.Column('vision_model', sa.String(100), nullable=False),
        sa.Column('is_low_confidence', sa.Boolean, nullable=False, server_default='false'),
        sa.Column('validated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    )
    op.create_index('idx_image_metadata_image', 'image_metadata', ['image_id'])
    op.create_index('idx_image_metadata_subject', 'image_metadata', ['subject'])
    op.create_index('idx_image_metadata_category', 'image_metadata', ['category'])
    op.execute('ALTER TABLE image_metadata ADD CONSTRAINT ck_confidence_range CHECK (confidence >= 0 AND confidence <= 1)')

    # Embeddings table (for Phase 3)
    op.create_table(
        'embeddings',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False),
        sa.Column('source_type', sa.String(50), nullable=False),
        sa.Column('source_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('vector', sa.dialects.postgresql.VECTOR(768), nullable=False),
        sa.Column('model', sa.String(100), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    )
    op.create_index('idx_embeddings_tenant', 'embeddings', ['tenant_id'])
    op.create_index('idx_embeddings_source', 'embeddings', ['source_type', 'source_id'])

    # Posts table (for Phase 3)
    op.create_table(
        'posts',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False),
        sa.Column('title', sa.String(500), nullable=False),
        sa.Column('content', sa.Text, nullable=False),
        sa.Column('embedding_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('embeddings.id'), nullable=True),
        sa.Column('expected_image_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('images.id'), nullable=True),
        sa.Column('is_evaluation', sa.Boolean, nullable=False, server_default='false'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    )
    op.create_index('idx_posts_tenant', 'posts', ['tenant_id'])

    # Suggestions table (for Phase 3)
    op.create_table(
        'suggestions',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('post_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('posts.id', ondelete='CASCADE'), nullable=False),
        sa.Column('image_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('images.id', ondelete='CASCADE'), nullable=False),
        sa.Column('similarity', sa.Numeric(6, 5), nullable=False),
        sa.Column('guard_decision', sa.String(50), nullable=False),
        sa.Column('guard_reasons', postgresql.JSONB, nullable=False, server_default='[]'),
        sa.Column('guard_explanation', sa.Text, nullable=True),
        sa.Column('vision_confidence', sa.Numeric(3, 2), nullable=True),
        sa.Column('rank', sa.Integer, nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    )
    op.create_index('idx_suggestions_post', 'suggestions', ['post_id'])
    op.create_index('idx_suggestions_decision', 'suggestions', ['guard_decision'])

    # Approvals table (for Phase 3)
    op.create_table(
        'approvals',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('suggestion_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('suggestions.id', ondelete='CASCADE'), nullable=False),
        sa.Column('decision', sa.String(20), nullable=False),
        sa.Column('reviewer_note', sa.Text, nullable=True),
        sa.Column('decided_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    )
    op.create_index('idx_approvals_suggestion', 'approvals', ['suggestion_id'])
    op.execute("ALTER TABLE approvals ADD CONSTRAINT ck_approval_decision CHECK (decision IN ('approved', 'rejected'))")

    # Jobs table
    op.create_table(
        'jobs',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False),
        sa.Column('type', sa.String(50), nullable=False),
        sa.Column('status', sa.String(50), nullable=False, server_default='pending'),
        sa.Column('progress', sa.Integer, nullable=False, server_default='0'),
        sa.Column('payload', postgresql.JSONB, nullable=False, server_default='{}'),
        sa.Column('error', sa.Text, nullable=True),
        sa.Column('idempotency_key', sa.String(255), unique=True, nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index('idx_jobs_tenant', 'jobs', ['tenant_id'])
    op.create_index('idx_jobs_status', 'jobs', ['status'])
    op.create_index('idx_jobs_idempotency', 'jobs', ['idempotency_key'])

    # Costs table
    op.create_table(
        'costs',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False),
        sa.Column('operation', sa.String(100), nullable=False),
        sa.Column('model', sa.String(100), nullable=False),
        sa.Column('related_type', sa.String(50), nullable=True),
        sa.Column('related_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('tokens_input', sa.Integer, nullable=True),
        sa.Column('tokens_output', sa.Integer, nullable=True),
        sa.Column('cost_usd', sa.Numeric(10, 6), nullable=False, server_default='0'),
        sa.Column('status', sa.String(50), nullable=False, server_default='success'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    )
    op.create_index('idx_costs_tenant', 'costs', ['tenant_id'])
    op.create_index('idx_costs_related', 'costs', ['related_type', 'related_id'])
    op.create_index('idx_costs_operation', 'costs', ['operation'])


def downgrade() -> None:
    op.drop_table('costs')
    op.drop_table('jobs')
    op.drop_table('approvals')
    op.drop_table('suggestions')
    op.drop_table('posts')
    op.drop_table('embeddings')
    op.drop_table('image_metadata')
    op.drop_table('images')
    op.drop_table('tenants')
    op.execute('DROP EXTENSION IF EXISTS vector')