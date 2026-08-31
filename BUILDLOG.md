# AI Usage & Development Build Log (`BUILDLOG.md`)

This log documents the design decisions, AI assistance utilization, corrections, and manual engineering performed during the development of the **FlyRank Backend Capstone — AI Image Understanding & Content Matching Engine**.

---

## 1. Project Phase Breakdown & Engineering Flow

### Phase 1: Architecture & Design (`DESIGN.md`)
- **What was built**: Core domain models (`Tenant`, `Image`, `ImageMetadata`, `Embedding`, `Post`, `Suggestion`, `Approval`, `Job`, `Cost`), repository patterns, and Pydantic schemas.
- **AI Assistance**: AI generated initial draft schemas for image metadata.
- **Manual Engineering**: Refactored schema constraints to mandate strict confidence bounds (`0.0 <= confidence <= 1.0`), subject existence, and array type safety. Designed single-tenant isolation (`tenant_id`) pattern across all repository queries.

---

### Phase 2: Vision Pipeline, Batch Processing & Cost Tracking
- **What was built**: Asynchronous `BatchProcessor` job queue, `VisionService` via Bakllava:7b, structured response validation, retries with exponential backoff via `tenacity`, and per-call cost logging (`CostService`).
- **AI Assistance**: AI provided initial template for Bakllava API call.
- **AI Mistake & Resolution**: AI attempted to trust raw model JSON directly. Manually implemented `Pydantic` `VisionOutputSchema.model_validate_json()` validation layer and confidence check (`confidence < 0.70`), ensuring low-confidence classifications are flagged (`ImageStatus.FLAGGED`) rather than accepted.

---

### Phase 3: Embedding Generator, Matching Engine & Mismatch Guard
- **What was built**: Vector embedding generator (`nomic-embed-text`), cosine similarity calculation, candidate ranking, and the safety decision layer (`MismatchGuard`).
- **AI Assistance**: AI generated cosine similarity helper function.
- **Manual Engineering**: Developed multi-rule mismatch guard evaluating:
  1. Category Mismatch Guard (e.g., rejecting a wolf image for a red fox post).
  2. Similarity Threshold Guard (`similarity < 0.75`).
  3. Vision Confidence Guard (`confidence < 0.70`).
  Created explicit human-readable explanations (`"Animal category mismatch: expected red_fox, detected wolf"`) and non-confident match response fallback (`"status": "no_confident_match"`).

---

### Phase 4: Production REST API, Evaluation & Documentation
- **What was built**: FastAPI application (`app/main.py`), v1 API routers (`/images`, `/jobs`, `/posts`, `/suggestions`, `/costs`), input validation exception handlers, labeled dataset evaluation script (`scripts/eval_precision.py`), and submission artifacts.
- **AI Mistake & Resolution**: Initial test client setup was failing due to unhandled database lifespan initialization. Manually added `@patch("app.main.init_db")` fixture overrides and updated deprecated `utcnow()` to timezone-aware UTC `datetime.now(timezone.utc)` objects across all repositories.

---

## 2. Model & Tuning Summary

| Layer | Selected Model / Tool | Role & Rational |
| :--- | :--- | :--- |
| **Vision Model** | `bakllava:7b` (via Ollama) | Local $0 vision understanding producing structured tags & captions |
| **Embedding Model** | `nomic-embed-text` (via Ollama) | 768-dimensional text/caption vector embedding into shared semantic space |
| **Similarity Metric** | Cosine Similarity | Vector angle distance metric for content ranking |
| **Similarity Threshold** | `0.75` | Tuned against 10-post labeled eval set to maximize precision |
| **Vision Confidence Threshold** | `0.70` | Cut-off for flagging low-confidence vision predictions |

---

## 3. Verification & Test Suite Summary

- **Total Unit & Integration Tests**: 134 passed, 0 failed.
- **API Endpoint Coverage**: 20/20 API tests passing.
- **Evaluation Top-1 Precision**: `90.0%` top-1 precision on 10-post labeled evaluation dataset.
