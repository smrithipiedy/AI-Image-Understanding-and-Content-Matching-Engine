# AI Image Understanding & Content Matching Engine - Design Document

## 1. Problem Statement

Build a trustworthy AI decision system that:
- Understands what is actually in images (not filenames or tags)
- Automatically tags/classifies images with structured metadata
- Matches images to blog posts based on semantic meaning
- Uses a mismatch guard to prevent incorrect recommendations
- Explains why recommendations are rejected
- Safely rejects uncertain matches instead of guessing
- Returns "no confident match" when no candidate passes the guard

**Core Example:**
- Blog post: "The behavior of red foxes"
- Correct image: A red fox
- Incorrect candidate: A gray wolf in a forest
- Expected result: REJECTED with explanation "Animal category mismatch: expected fox, detected wolf"

## 2. Architecture Overview

### Layered Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        HTTP LAYER                             │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐          │
│  │   Routes    │  │ Validation  │  │  Responses  │          │
│  │ Controllers │  │  (Pydantic) │  │  Formatting │          │
│  └─────────────┘  └─────────────┘  └─────────────┘          │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                        LOGIC LAYER                            │
│  ┌──────────────┐ ┌──────────────┐ ┌────────────────────┐   │
│  │ Vision       │ │ Embedding    │ │ Mismatch Guard     │   │
│  │ Processing   │ │ Generation   │ │ (Core Safety)      │   │
│  └──────────────┘ └──────────────┘ └────────────────────┘   │
│  ┌──────────────┐ ┌──────────────┐ ┌────────────────────┐   │
│  │ Similarity   │ │ Ranking      │ │ Batch Processing   │   │
│  │ Calculation  │ │              │ │ & Cost Tracking    │   │
│  └──────────────┘ └──────────────┘ └────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                         DATA LAYER                            │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐            │
│  │  Database   │ │ Repositories│ │  Migrations │            │
│  │  Models     │ │ (Data Access)│ │             │            │
│  └─────────────┘ └─────────────┘ └─────────────┘            │
└─────────────────────────────────────────────────────────────┘
```

### Conceptual Pipeline

```
IMAGES                          POST TEXT
  │                                │
  ▼                                ▼
VISION MODEL                    EMBED POST
  │                                │
  ▼                                ▼
STRUCTURED VALIDATED         post_vectors
METADATA (Pydantic)                │
  │                                │
  ├── image_metadata              │
  │                                │
  └── embed(caption)               │
       │                            │
       ▼                            │
   image_vectors ◄──────────────────┘
       │
       ▼
GET /posts/:id/images
       │
       ▼
SIMILARITY RANKING (cosine)
       │
       ▼
MISMATCH GUARD ◄──────────────────────┐
       │                               │
       ├── ACCEPTED → Suggested + why   │
       ├── REJECTED → Explanation       │
       └── NO CONFIDENT MATCH           │
       │                               │
       ▼                               │
REVIEW API                            │
       │                               │
       ├── approve                     │
       ├── reject                      │
       └── inspect                     │
```

## 3. Data Model

### Database Schema (PostgreSQL + pgvector)

```sql
-- Tenants (multi-tenant isolation)
CREATE TABLE tenants (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL UNIQUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Images
CREATE TABLE images (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    url TEXT NOT NULL,
    filename VARCHAR(255) NOT NULL,
    sha256 CHAR(64) NOT NULL,
    source_provider VARCHAR(100) NOT NULL,  -- 'unsplash', 'pexels'
    source_url TEXT NOT NULL,
    license VARCHAR(100) NOT NULL,          -- 'Unsplash License', 'Pexels License'
    expected_category VARCHAR(100),         -- for eval: 'red_fox', 'wolf', etc.
    status VARCHAR(50) NOT NULL DEFAULT 'pending',  -- pending, processing, completed, failed, flagged
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Image Metadata (structured vision output)
CREATE TABLE image_metadata (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    image_id UUID NOT NULL REFERENCES images(id) ON DELETE CASCADE,
    subject VARCHAR(255) NOT NULL,           -- "red fox"
    category VARCHAR(100) NOT NULL,          -- "animal"
    attributes JSONB NOT NULL DEFAULT '[]',  -- ["orange fur", "wild", "forest"]
    caption TEXT NOT NULL,                   -- "A red fox standing in a forest"
    confidence NUMERIC(3,2) NOT NULL CHECK (confidence >= 0 AND confidence <= 1),
    vision_model VARCHAR(100) NOT NULL,      -- "bakllava:7b"
    is_low_confidence BOOLEAN NOT NULL DEFAULT FALSE,
    validated_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Embeddings (both images and posts)
CREATE TABLE embeddings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    source_type VARCHAR(50) NOT NULL,        -- 'image_caption', 'post_text'
    source_id UUID NOT NULL,                 -- references images.id or posts.id
    vector VECTOR(768) NOT NULL,             -- nomic-embed-text = 768 dims
    model VARCHAR(100) NOT NULL,             -- "nomic-embed-text"
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Blog Posts
CREATE TABLE posts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    title VARCHAR(500) NOT NULL,
    content TEXT NOT NULL,
    embedding_id UUID REFERENCES embeddings(id),
    expected_image_id UUID REFERENCES images(id),  -- for evaluation ground truth
    is_evaluation BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Suggestions (match results)
CREATE TABLE suggestions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    post_id UUID NOT NULL REFERENCES posts(id) ON DELETE CASCADE,
    image_id UUID NOT NULL REFERENCES images(id) ON DELETE CASCADE,
    similarity NUMERIC(6,5) NOT NULL,        -- cosine similarity 0-1
    guard_decision VARCHAR(50) NOT NULL,     -- 'accepted', 'rejected', 'no_confident_match'
    guard_reasons JSONB NOT NULL DEFAULT '[]',  -- ["category_mismatch", "similarity_below_threshold"]
    guard_explanation TEXT,                   -- human-readable
    vision_confidence NUMERIC(3,2),
    rank INTEGER NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Approvals/Rejections (review workflow)
CREATE TABLE approvals (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    suggestion_id UUID NOT NULL REFERENCES suggestions(id) ON DELETE CASCADE,
    decision VARCHAR(20) NOT NULL CHECK (decision IN ('approved', 'rejected')),
    reviewer_note TEXT,
    decided_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Background Jobs
CREATE TABLE jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    type VARCHAR(50) NOT NULL,               -- 'image_ingestion', 'embedding_generation'
    status VARCHAR(50) NOT NULL DEFAULT 'pending',  -- pending, processing, completed, failed
    progress INTEGER NOT NULL DEFAULT 0,      -- 0-100
    payload JSONB NOT NULL DEFAULT '{}',
    error TEXT,
    idempotency_key VARCHAR(255) UNIQUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ
);

-- Cost Tracking
CREATE TABLE costs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    operation VARCHAR(100) NOT NULL,         -- 'vision_classification', 'embedding_generation'
    model VARCHAR(100) NOT NULL,             -- 'bakllava:7b', 'nomic-embed-text'
    related_type VARCHAR(50),                -- 'image', 'post', 'job'
    related_id UUID,
    tokens_input INTEGER,
    tokens_output INTEGER,
    cost_usd NUMERIC(10,6) NOT NULL DEFAULT 0,
    status VARCHAR(50) NOT NULL DEFAULT 'success',  -- success, failed
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_images_tenant ON images(tenant_id);
CREATE INDEX idx_images_status ON images(status);
CREATE INDEX idx_image_metadata_image ON image_metadata(image_id);
CREATE INDEX idx_image_metadata_subject ON image_metadata(subject);
CREATE INDEX idx_image_metadata_category ON image_metadata(category);
CREATE INDEX idx_embeddings_tenant ON embeddings(tenant_id);
CREATE INDEX idx_embeddings_source ON embeddings(source_type, source_id);
CREATE INDEX idx_posts_tenant ON posts(tenant_id);
CREATE INDEX idx_suggestions_post ON suggestions(post_id);
CREATE INDEX idx_suggestions_decision ON suggestions(guard_decision);
CREATE INDEX idx_approvals_suggestion ON approvals(suggestion_id);
CREATE INDEX idx_jobs_tenant ON jobs(tenant_id);
CREATE INDEX idx_jobs_status ON jobs(status);
CREATE INDEX idx_jobs_idempotency ON jobs(idempotency_key);
CREATE INDEX idx_costs_tenant ON costs(tenant_id);
CREATE INDEX idx_costs_related ON costs(related_type, related_id);
```

## 4. API Surface

### Endpoints

| Method | Path | Description | Request | Response |
|--------|------|-------------|---------|----------|
| POST | `/api/v1/images/ingest` | Trigger batch image ingestion | `{ "urls": [...] }` | `{ "job_id": "...", "status": "pending" }` |
| GET | `/api/v1/images` | List images with metadata | Query: `tenant_id`, `status`, `limit`, `offset` | `{ "images": [...], "total": N }` |
| GET | `/api/v1/images/{id}` | Get image details | - | Image + metadata |
| POST | `/api/v1/posts` | Create blog post | `{ "title": "...", "content": "..." }` | Post with ID |
| GET | `/api/v1/posts/{id}/images` | Get matched images (with guard) | Query: `top_k` | `{ "match": {...}, "status": "accepted|no_confident_match", "reasons": [...] }` |
| POST | `/api/v1/suggestions/{id}/review` | Approve/reject suggestion | `{ "decision": "approved|rejected", "note": "..." }` | Approval record |
| GET | `/api/v1/jobs/{id}` | Get job status | - | Job with progress |
| GET | `/api/v1/costs` | Get cost log | Query: `tenant_id`, `operation`, `limit` | Cost records |
| POST | `/api/v1/eval/run` | Run evaluation | - | `{ "precision": 0.9, "total": 10, "correct": 9 }` |

### Request/Response Schemas (Pydantic)

```python
# Vision output schema (validated from model)
class VisionOutput(BaseModel):
    subject: str = Field(..., min_length=1, max_length=255)
    category: str = Field(..., min_length=1, max_length=100)
    attributes: List[str] = Field(default_factory=list)
    caption: str = Field(..., min_length=1)
    confidence: float = Field(..., ge=0.0, le=1.0)

# API Requests
class ImageIngestRequest(BaseModel):
    urls: List[HttpUrl] = Field(..., min_length=1, max_length=50)

class PostCreateRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=500)
    content: str = Field(..., min_length=1)

class SuggestionReviewRequest(BaseModel):
    decision: Literal["approved", "rejected"]
    note: Optional[str] = None

# API Responses
class ImageResponse(BaseModel):
    id: UUID
    url: str
    filename: str
    status: str
    metadata: Optional[ImageMetadataResponse]

class ImageMetadataResponse(BaseModel):
    subject: str
    category: str
    attributes: List[str]
    caption: str
    confidence: float
    is_low_confidence: bool

class MatchResponse(BaseModel):
    match: Optional[ImageMatch] = None
    status: Literal["accepted", "no_confident_match"]
    reasons: List[str] = Field(default_factory=list)

class ImageMatch(BaseModel):
    image_id: UUID
    image_url: str
    similarity: float
    subject: str
    category: str
    explanation: str  # why accepted

class NoMatchResponse(BaseModel):
    match: None
    status: Literal["no_confident_match"]
    reasons: List[str]  # e.g., ["similarity_below_threshold", "subject_mismatch"]

class EvaluationResponse(BaseModel):
    total_posts: int
    correct_top1: int
    top1_precision: float
    threshold_used: float
    details: List[EvaluationDetail]
```

## 5. Non-Goals (Explicit)

Per CLAUDE.md Section 28, the following are explicitly NOT implemented:
- Full frontend/UI
- User authentication/authorization
- Social features, image uploading platform
- Image editing, recommendation feeds, chat interface
- Autonomous agent swarms, multiple AI providers
- Model comparison dashboard
- Massive vector database infrastructure
- Cloud deployment infrastructure (unless required)
- Payment/billing, analytics dashboard, notification system
- Unnecessary microservices, Kubernetes, Redis (unless genuinely required)
- Complex distributed architecture, unnecessary abstractions
- Unrelated features

## 6. Matching Strategy

### Semantic Embedding
- Both image captions and post text embedded with **nomic-embed-text** (768-dim)
- Same model ensures shared semantic space
- Stored in `embeddings` table with pgvector

### Similarity Calculation
- **Cosine similarity** between post embedding and image caption embeddings
- Formula: `similarity = (A · B) / (||A|| * ||B||)`
- Rank candidates by descending similarity

### Equivalent Concepts
- "red fox" ≈ "Vulpes vulpes" ≈ "wild fox species"
- Semantic closeness handled by embedding model
- No keyword matching, no filename matching

## 7. Mismatch Guard Rules

### Guard Module: `services/mismatch_guard.py`

The guard is a **separate, testable module** with explicit rules.

### Input to Guard
```python
class GuardInput(BaseModel):
    post: Post                    # has title, content, embedding
    candidate: ImageCandidate     # image_id, similarity, metadata, vision_confidence
    thresholds: GuardThresholds
```

### Thresholds (Configurable, Tuned on Eval Data)
```python
class GuardThresholds(BaseModel):
    similarity_threshold: float = 0.75      # tuned via eval
    vision_confidence_threshold: float = 0.70  # minimum vision confidence
    category_match_required: bool = True
    subject_match_required: bool = True
```

### Guard Logic (Deterministic, Ordered)

```python
def evaluate_guard(input: GuardInput) -> GuardResult:
    reasons = []
    
    # Rule 1: Vision confidence too low
    if input.candidate.vision_confidence < input.thresholds.vision_confidence_threshold:
        reasons.append(f"vision_confidence_below_threshold ({input.candidate.vision_confidence:.2f} < {input.thresholds.vision_confidence_threshold})")
    
    # Rule 2: Category mismatch
    if input.thresholds.category_match_required:
        post_category = extract_category_from_post(input.post)
        if post_category and post_category != input.candidate.category:
            reasons.append(f"category_mismatch: expected {post_category}, detected {input.candidate.category}")
    
    # Rule 3: Subject mismatch (for animals)
    if input.thresholds.subject_match_required:
        post_subject = extract_subject_from_post(input.post)
        if post_subject and post_subject != input.candidate.subject:
            reasons.append(f"subject_mismatch: expected {post_subject}, detected {input.candidate.subject}")
    
    # Rule 4: Similarity below threshold
    if input.candidate.similarity < input.thresholds.similarity_threshold:
        reasons.append(f"similarity_below_threshold ({input.candidate.similarity:.3f} < {input.thresholds.similarity_threshold})")
    
    # Decision
    if reasons:
        return GuardResult(
            decision="rejected",
            reasons=reasons,
            explanation=format_rejection_explanation(reasons, input.candidate)
        )
    else:
        return GuardResult(
            decision="accepted",
            reasons=[],
            explanation=format_acceptance_explanation(input.candidate)
        )
```

### Rejection Explanation Format
- **Category mismatch**: "Animal category mismatch: expected fox, detected wolf"
- **Subject mismatch**: "Subject mismatch: expected red fox, detected gray wolf"
- **Low vision confidence**: "Low vision confidence: 0.55 (threshold: 0.70)"
- **Low similarity**: "Semantic similarity 0.62 below threshold 0.75"
- **Multiple**: Combined with "; "

### No-Confident-Match Behavior
When NO candidate passes guard for a post:
```python
return NoMatchResponse(
    match=None,
    status="no_confident_match",
    reasons=[
        "similarity_below_threshold" if all below threshold else "",
        "subject_mismatch" if subjects don't match else "",
        "vision_confidence_below_threshold" if all low confidence else ""
    ]
)
```

## 8. Threshold Tuning Approach

### Methodology
1. **Create evaluation dataset**: 10+ posts with independently defined ground-truth image IDs
2. **Define threshold grid**: e.g., similarity ∈ [0.60, 0.65, 0.70, 0.75, 0.80, 0.85], vision_conf ∈ [0.60, 0.65, 0.70, 0.75]
3. **Evaluate each combination**: Run matching + guard on all eval posts
4. **Record results**: For each threshold combo, record top-1 precision, rejection rate, no-match rate
5. **Select threshold**: Choose highest similarity threshold that maintains ≥80% precision while keeping no-match rate reasonable
6. **Document**: Record all tested thresholds, results, and selection rationale in README

### Selection Rule
> "Select the highest similarity threshold that achieves top-1 precision ≥ 80% on the evaluation set, with vision confidence threshold fixed at 0.70."

This is defensible because:
- Higher threshold = fewer false accepts (safer)
- Precision target ensures quality
- Fixed vision confidence prevents over-tuning

## 9. Background Batch Processing

### Job Queue Design (DB-based, No Redis)
```python
class JobProcessor:
    async def process_image_batch(job_id: UUID):
        job = await get_job(job_id)
        job.status = "processing"
        job.started_at = now()
        
        for image_url in job.payload["urls"]:
            # Idempotency: check if already processed
            existing = await get_image_by_url(image_url)
            if existing and existing.status == "completed":
                continue  # skip, already done
            
            # Process single image
            await process_single_image(image_url, job.tenant_id)
            job.progress = calculate_progress()
            await update_job(job)
        
        job.status = "completed"
        job.completed_at = now()
```

### Retry Logic
- Max 3 retries per image
- Exponential backoff: 1s, 2s, 4s
- Idempotency key per image URL prevents duplicate processing
- Failed images marked `status = 'failed'` with error logged

### Cost Tracking Per Call
```python
async def track_cost(operation: str, model: str, related_id: UUID, tokens: int):
    # For local Ollama: cost_usd = 0, but still record the call
    cost = Cost(
        operation=operation,
        model=model,
        related_id=related_id,
        tokens_input=tokens,
        cost_usd=0.0,
        status="success"
    )
    await save_cost(cost)
```

## 10. Dataset Plan (~50 Images)

### Categories (5 core, ~10 each)
| Category | Expected Count | Search Terms |
|----------|----------------|--------------|
| red_fox | 10 | "red fox", "vulpes vulpes", "fox in forest" |
| wolf | 8 | "gray wolf", "wolf in snow", "wild wolf" |
| dog | 8 | "dog", "golden retriever", "husky" |
| bear | 8 | "brown bear", "grizzly bear", "black bear" |
| deer | 8 | "deer", "white-tailed deer", "red deer" |
| **Other** | **8** | eagle, rabbit, squirrel, etc. |
| **Total** | **~50** | |

### Image Metadata Recorded Per Image
- `source_provider`: "unsplash" or "pexels"
- `source_url`: Direct image URL
- `license`: "Unsplash License" or "Pexels License"
- `sha256`: File checksum for reproducibility
- `expected_category`: Ground-truth category for eval

### Evaluation Posts (10+)
| Post Title | Expected Image Category | Ground Truth Image ID |
|------------|------------------------|----------------------|
| "The behavior of red foxes" | red_fox | [UUID] |
| "Wolf pack dynamics in winter" | wolf | [UUID] |
| "Golden retriever training tips" | dog | [UUID] |
| "Brown bear hibernation patterns" | bear | [UUID] |
| "Deer migration in autumn" | deer | [UUID] |
| "Red fox hunting techniques" | red_fox | [UUID] |
| "Arctic wolf survival" | wolf | [UUID] |
| "Bear safety in national parks" | bear | [UUID] |
| "Urban fox adaptation" | red_fox | [UUID] |
| "Wildlife photography: deer" | deer | [UUID] |
| "No-match test post" | N/A (no suitable image) | NULL |

### Download Script
- Python script using `requests` + `hashlib`
- Reads CSV/JSON manifest with URLs and metadata
- Downloads to `data/images/`
- Records metadata to DB on ingestion
- Verifies checksums
- Idempotent (skips existing files)

## 11. Technology Stack Summary

| Component | Choice | Version |
|-----------|--------|---------|
| Language | Python | 3.11+ |
| Framework | FastAPI | 0.109+ |
| Validation | Pydantic | 2.6+ |
| Database | PostgreSQL | 16 |
| Vector Ext | pgvector | 0.7+ |
| ORM | SQLAlchemy | 2.0+ |
| Migrations | Alembic | 1.13+ |
| Vision | Ollama + bakllava:7b | Latest |
| Embeddings | Ollama + nomic-embed-text | Latest |
| Job Queue | Custom DB-based | - |
| Config | python-dotenv | - |
| Testing | pytest | 8.0+ |

## 12. Environment Variables (.env.example)

```bash
# Database
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/flyrank

# Ollama
OLLAMA_BASE_URL=http://localhost:11434
VISION_MODEL=bakllava:7b
EMBEDDING_MODEL=nomic-embed-text

# App
APP_HOST=0.0.0.0
APP_PORT=8000
TENANT_ID=demo-tenant

# Budget Guard (in USD, $0 for local)
MAX_BUDGET_USD=0.00

# Thresholds (tuned after eval)
SIMILARITY_THRESHOLD=0.75
VISION_CONFIDENCE_THRESHOLD=0.70

# Logging
LOG_LEVEL=INFO
```

## 13. Docker Compose (for local dev)

```yaml
version: '3.8'
services:
  postgres:
    image: pgvector/pgvector:pg16
    environment:
      POSTGRES_DB: flyrank
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 5s
      timeout: 5s
      retries: 5

  ollama:
    image: ollama/ollama:latest
    ports:
      - "11434:11434"
    volumes:
      - ollama_data:/root/.ollama
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: all
              capabilities: [gpu]

volumes:
  postgres_data:
  ollama_data:
```

## 14. Phase 1 Gate Verification

**Phase 1 Complete When:**
- [ ] DESIGN.md committed with all sections above
- [ ] Database schema reviewed and matches requirements
- [ ] API endpoints cover all required functionality
- [ ] Mismatch guard rules are explicit and testable
- [ ] Threshold tuning methodology is documented and defensible
- [ ] Dataset plan specifies ~50 images across 5+ categories with licensing info
- [ ] Non-goals are explicitly listed
- [ ] Architecture diagram is clear

---

*This design document serves as the implementation blueprint. All subsequent phases reference this document.*