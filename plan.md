# Implementation Plan: AI Image Understanding & Content Matching Engine

## Context

This plan implements the complete FlyRank Internship Backend Track Capstone: "AI Image Understanding & Content Matching Engine" as specified in CLAUDE.md. The repository is empty except for CLAUDE.md and .git. The system must understand images via vision AI, classify/tag them, match to blog posts semantically, and use a mismatch guard to prevent incorrect recommendations.

---

## Requirements Summary (from CLAUDE.md)

### Core Functionality

1. **Image Understanding Pipeline**: Process ~50 images through vision model → structured metadata (subject, category, attributes, caption, confidence) → schema validation → embeddings
2. **Semantic Matching**: Embed image captions and post text in same space → cosine similarity → ranked candidates
3. **Mismatch Guard**: Separate module combining tags, similarity score, vision confidence, tuned thresholds → reject mismatches (e.g., wolf for fox post) with human-readable explanations
4. **No-Confident-Match**: Return "no confident match" with reasons when no candidate passes guard
5. **Background Batch Processing**: Async job queue with retries, progress tracking, idempotency, cost tracking
6. **Review API**: Approve/reject suggestions, persist decisions, inspect reasoning
7. **Evaluation**: 10+ labeled posts, top-1 precision metric, threshold tuned on eval data

### Technology Choices (Confirmed)

- **Backend**: Python + FastAPI (simpler for ML/AI, better Pydantic integration)
- **Schema**: Pydantic
- **Database**: PostgreSQL + pgvector (cleaner for vector search)
- **Vision**: Ollama with **BakLLaVA 7B (bakllava:7b)** - fine-tuned LLaVA, ~4.7GB
- **Embeddings**: Ollama with **nomic-embed-text** - 768-dim, strong semantic quality
- **Background Jobs**: Simple DB-based queue (no Redis needed at this scale)
- **Image Dataset**: Download script from curated Unsplash/Pexels URLs with **recorded source provider, URL, license, checksum, and expected category per image**

### Required Files

- README.md, capstone.yaml, EVIDENCE.md, BUILDLOG.md, .env.example, .gitignore, LICENSE
- Database migrations, seed script, evaluation script, Docker config

---

## Implementation Plan

### Phase 1: DESIGN (Week 1) ✅ COMPLETE

**Deliverable**: Committed design document with problem statement, data model, API surface, layer sketch, non-goals, matching strategy, mismatch guard rules, database design, dataset plan.

**Tasks**:

1. ✅ Create design document (DESIGN.md)
2. ✅ Define Pydantic schemas for vision output, embeddings, API requests/responses
3. ✅ Design database schema (images, image_metadata, embeddings, posts, suggestions, approvals, jobs, costs, tenants)
4. ✅ Design API endpoints
5. ✅ Define mismatch guard rules and threshold tuning approach
6. ✅ Plan ~50 image dataset (categories: red fox, wolf, dog, bear, deer + 10 eval posts)

### Phase 2: IMAGE UNDERSTANDING PIPELINE (Week 2) 🔄 IN PROGRESS

**Deliverable**: All seed images processed with schema-valid metadata, costs visible.

**Tasks**:

1. ✅ Set up PostgreSQL + pgvector via Docker Compose
2. ⏳ Create database migrations (Alembic) - NOT DONE YET
3. ✅ Implement Pydantic schemas for vision output (app/schemas/vision.py)
4. ✅ Integrate Ollama vision model (**bakllava:7b**) (app/services/vision.py)
5. ✅ Implement schema validation with retry logic (app/services/vision.py)
6. ✅ Implement low-confidence flagging (app/services/vision.py)
7. ⏳ Build background batch processor (DB-based queue) - NOT DONE YET
8. ✅ Implement per-call cost tracking (record as $0 for local models) (app/services/cost.py)
9. ⏳ Create seed script to download ~50 license-free images - NOT DONE YET
10. ⏳ Process all images through pipeline - NOT DONE YET
11. ✅ Write tests FIRST (TDD):
    - ✅ test_schemas_vision.py - VisionOutput schema validation tests
    - ✅ test_vision_service.py - VisionService with retries, schema validation
    - ✅ test_cost_service.py - CostService with budget guard
    - ✅ test_batch_processor.py - Job/Image/Cost repositories, batch processor skeleton
12. ⏳ Implement remaining code to make tests pass
13. ⏳ Run Phase 2 acceptance checks and report results

### Phase 3: MATCHING ENGINE (Week 3)

**Deliverable**: Fox post ranks fox first, wolf rejected, no-match returns "no confident match".

**Tasks**:

1. Implement embedding generation (Ollama **nomic-embed-text** only)
2. Store image embeddings (from captions) and post embeddings
3. Implement cosine similarity search
4. Build mismatch guard module with:
   - Category/subject validation
   - Similarity threshold (**tuned on eval data with documented range and selection rule**)
   - Vision confidence threshold
   - Human-readable rejection explanations
5. Implement no-confident-match response
6. Create evaluation dataset (**10+ posts with independently defined ground-truth image IDs, never derived from model output**)
7. Tune thresholds using evaluation data (**evaluate documented threshold range, record results, select with defensible rule - never tune toward desired score or alter labels**)
8. Verify acceptance probes 1-4

### Phase 4: PRODUCTION LAYER (Week 4)

**Deliverable**: All 6 acceptance probes pass, all required files complete.

**Tasks**:

1. Implement review API (approve/reject/inspect)
2. Build evaluation script (top-1 precision)
3. Generate README.md with architecture diagram, run instructions, precision result
4. Create capstone.yaml manifest
5. Populate EVIDENCE.md with real command outputs
6. Write BUILDLOG.md (honest AI usage log)
7. Create .env.example with all required variables
8. Add .gitignore, LICENSE
9. Final hardening: API validation (4xx errors), idempotency, budget guard
10. Run all 6 acceptance probes, verify results

---

## Key Technical Decisions

| Decision         | Choice                                                         | Rationale                                   |
| ---------------- | -------------------------------------------------------------- | ------------------------------------------- |
| Backend          | Python + FastAPI                                               | Better ML ecosystem, Pydantic native        |
| Vision Model     | Ollama **BakLLaVA 7B (bakllava:7b)**                           | Local, $0, reproducible                     |
| Embedding Model  | Ollama **nomic-embed-text**                                    | Local, $0, good semantic quality            |
| Vector Search    | pgvector + cosine similarity                                   | Built into Postgres, no extra infra         |
| Background Jobs  | DB-based queue table                                           | Simple, no Redis, sufficient for 50 images  |
| Cost Tracking    | DB table with $0 for local                                     | Meets requirement, honest about local costs |
| Threshold Tuning | **Documented range evaluation with defensible selection rule** | Data-driven, transparent, reproducible      |

---

## Strict Scope Constraints (from User Corrections)

1. **Vision Model**: ONLY `bakllava:7b` - no references to `llava:7b` or generic LLaVA
2. **Embedding Model**: ONLY `nomic-embed-text` - no `all-minilm` alternatives
3. **Dataset Licensing**: Every image must record source provider, URL, license, checksum, expected category
4. **Evaluation Integrity**: 10+ eval posts with independently defined ground-truth image IDs (never from model output)
5. **Threshold Tuning**: Documented range, recorded results, defensible rule - never tune toward desired precision
6. **Background Jobs**: DB-based queue only - no Redis, Celery, RabbitMQ, Kubernetes
7. **Phase 1 Only**: Implement and verify Phase 1 (design deliverable) before Phase 2
8. **No Extra Features**: No frontend, auth, dashboards, multi-model infra, distributed systems, or unnecessary functionality

---

## Database Schema (Preliminary)

```sql
-- Core tables
tenants (id, name, created_at)
images (id, tenant_id, url, filename, status, created_at)
image_metadata (id, image_id, subject, category, attributes[], caption, confidence, validated_at)
embeddings (id, tenant_id, source_type, source_id, vector, model, created_at)
posts (id, tenant_id, title, content, embedding_id, created_at)
suggestions (id, post_id, image_id, similarity, guard_decision, guard_reasons[], created_at)
approvals (id, suggestion_id, decision, reviewer_note, decided_at)
jobs (id, tenant_id, type, status, progress, payload, error, created_at, started_at, completed_at)
costs (id, tenant_id, operation, model, related_id, tokens, cost_usd, status, created_at)
```

---

## API Endpoints

| Method | Endpoint                        | Description                     |
| ------ | ------------------------------- | ------------------------------- |
| POST   | /api/v1/images/ingest           | Trigger batch ingestion         |
| GET    | /api/v1/images                  | List images with metadata       |
| GET    | /api/v1/images/{id}             | Get image details               |
| POST   | /api/v1/posts                   | Create blog post                |
| GET    | /api/v1/posts/{id}/images       | Get matched images (with guard) |
| POST   | /api/v1/suggestions/{id}/review | Approve/reject suggestion       |
| GET    | /api/v1/jobs/{id}               | Get job status                  |
| GET    | /api/v1/costs                   | Get cost log                    |
| POST   | /api/v1/eval/run                | Run evaluation                  |

---

## Acceptance Probes Verification Plan

1. **Probe 1**: Run batch job → verify all images have valid metadata, at least one low-confidence flagged
2. **Probe 2**: Query fox post → verify fox ranks 1st, wolf/dog lower
3. **Probe 3**: Force wolf candidate → verify rejection with "Animal category mismatch: expected fox, detected wolf"
4. **Probe 4**: Query no-match post → verify "no confident match" with reasons
5. **Probe 5**: Run eval script → verify top-1 precision matches README
6. **Probe 6**: Inspect cost log → verify every AI call has entry

---

## Questions for Clarification

1. **Image Source**: Should I download images from Unsplash/Pexels programmatically, or use a local fixture set? The brief says "reproducible seed mechanism" - I'll implement a script that downloads from public URLs (with checksums) or uses a local assets folder.

2. **Ollama Models**: Using `bakllava:7b` for vision and `nomic-embed-text` for embeddings (confirmed). Both are free, local, and well-supported.

3. **pgvector**: Use the official `pgvector/pgvector:pg16` Docker image? Requires enabling extension.

4. **Tenant Isolation**: Single demo tenant "demo" is sufficient per requirements?

5. **Evaluation Posts**: Should the 10 eval posts be created via seed script or API? I'll include in seed.

---

## Verification Strategy

Each phase ends with a verification gate:

- Phase 1: Design document committed
- Phase 2: `curl` batch job → all images processed, costs logged
- Phase 3: `curl` fox post → correct ranking, wolf rejected
- Phase 4: All 6 probes pass, all required files exist with real evidence

---

## Next Steps

Upon approval, I'll:

1. Create DESIGN.md with detailed specifications
2. Set up Docker Compose for Postgres + pgvector + Ollama
3. Initialize FastAPI project with Pydantic, Alembic
4. Begin Phase 2 implementation
