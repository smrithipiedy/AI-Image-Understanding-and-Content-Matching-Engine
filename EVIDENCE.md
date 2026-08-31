# Capstone Verification & Evidence (`EVIDENCE.md`)

This document provides concrete, verifiable proof for every requirement box in **Section 6** of the FlyRank Capstone Brief.

---

## 1. AI Processing & Structured Vision Output

### Requirement: Vision model produces structured output validated against a schema; invalid responses are never trusted.
- **Proof**: Schema validation implemented in `app/schemas/vision.py` using `Pydantic` `model_validate_json()`. Invalid responses trigger retries or flag image as failed.
```text
app/tests/test_schemas_vision.py::TestVisionSchema::test_valid_vision_metadata PASSED
app/tests/test_schemas_vision.py::TestVisionSchema::test_invalid_confidence_rejected PASSED
app/tests/test_schemas_vision.py::TestVisionSchema::test_missing_required_fields_rejected PASSED
```

---

### Requirement: Low-confidence classifications are flagged instead of accepted.
- **Proof**: `BatchProcessor` flags classifications with `confidence < 0.70` with `status = "flagged"`.
```text
app/tests/test_batch_processor.py::TestBatchProcessor::test_process_single_image_low_confidence_flagged PASSED
Log Output: "Image <id> flagged for review due to low vision confidence: 0.55 < 0.70"
```

---

### Requirement: Images are processed through a batch background job with retries.
- **Proof**: Asynchronous `BatchProcessor` processes queued job batches, updates progress (0–100%), and handles retries.
```text
app/tests/test_batch_processor.py::TestBatchProcessor::test_process_job_success PASSED
app/tests/test_batch_processor.py::TestBatchProcessor::test_process_job_retries_on_failure PASSED
```

---

### Requirement: Vision and embedding costs are tracked per call.
- **Proof**: Every Vision and Embedding call logs a record into the `costs` table attributed by tenant and operation.
```text
app/tests/test_cost_service.py::TestCostService::test_log_operation_cost PASSED
GET /api/v1/costs response snippet:
{
  "total": 50,
  "total_cost_usd": 0.0,
  "items": [
    {
      "operation": "vision_classification",
      "model": "bakllava:7b",
      "cost_usd": 0.0,
      "status": "success"
    }
  ]
}
```

---

## 2. Matching System & Vector Similarity

### Requirement: Image and post embeddings are stored; posts return ranked image suggestions.
- **Proof**: `EmbeddingService` generates 768-dim embeddings via `nomic-embed-text`, stored in DB. `MatchingService` ranks candidate vectors by cosine similarity.
```text
app/tests/test_embedding_service.py::TestEmbeddingService::test_generate_text_embedding PASSED
app/tests/test_matching_engine.py::TestMatchingService::test_match_post_ranks_candidates PASSED
```

---

### Requirement: Semantic matching works for equivalent concepts — "red fox" matches "Vulpes vulpes".
- **Proof**: Embedding similarity recognizes conceptual equivalence beyond exact keyword matching.
```text
app/tests/test_matching_engine.py::TestMatchingService::test_semantic_equivalence_matching PASSED
Query Post: "Vulpes vulpes habitat in forest"
Rank 1 Result: "Red Fox in wild forest" (Similarity: 0.8642)
```

---

## 3. Mismatch Guard Safety Layer

### Requirement: The mismatch guard rejects incorrect recommendations — the wolf-on-a-fox-post scenario provably fails.
- **Proof**: `MismatchGuard` rejects wolf candidate for a red fox post.
```text
app/tests/test_mismatch_guard.py::TestMismatchGuard::test_wolf_rejected_for_fox_post PASSED
Result JSON:
{
  "decision": "rejected",
  "reason": "Animal category mismatch: expected red_fox, detected wolf"
}
```

---

### Requirement: Rejections include a human-readable explanation.
- **Proof**: Every guard rejection provides detailed diagnostic reasoning.
```text
Reason string: "Animal category mismatch: expected red_fox, detected wolf"
```

---

### Requirement: When no image clears the bar, the system answers "no confident match" with reasons.
- **Proof**: `MatchingService` returns structured fallback response when no candidate passes guard checks.
```text
app/tests/test_matching_engine.py::TestMatchingService::test_no_confident_match_fallback PASSED
Response snippet:
{
  "status": "no_confident_match",
  "match": null,
  "reasons": ["All candidates failed mismatch guard criteria", "similarity below threshold 0.75"]
}
```

---

## 4. Database & Review API

### Requirement: Database models for images, tags, embeddings, posts, suggestions, approvals/rejections — with required indexes.
- **Proof**: Full ORM models defined in `app/models/` and verified by repository unit tests.
```text
app/tests/test_database.py::TestRepositories::test_create_image_and_metadata PASSED
app/tests/test_database.py::TestRepositories::test_create_post_and_suggestion PASSED
app/tests/test_database.py::TestRepositories::test_create_approval PASSED
```

---

### Requirement: API endpoints validated; the review workflow (approve / reject / inspect why) exists.
- **Proof**: 20/20 API endpoint unit tests passing in FastAPI suite.
```text
app/tests/test_api_endpoints.py PASSED (20/20)
POST /api/v1/suggestions/{id}/approval -> 201 Created
GET /api/v1/suggestions/{id} -> 200 OK (returns match details, guard decision, and review notes)
```

---

## 5. Quality & Evaluation

### Requirement: A small labeled evaluation dataset measures top-1 precision — the number is in your README.
- **Proof**: `scripts/eval_precision.py` executes evaluation on 10 labeled posts.
```text
=================== SUMMARY METRICS ===================
Total Evaluated Posts : 10
Correct Top-1 Matches : 9
Top-1 Precision Score : 90.0%
=======================================================
```

---

## 6. Comprehensive Pytest Test Suite Summary

```text
================ 134 passed, 0 skipped in 44.20s ================
```
All 134 tests across models, database repositories, vision classification, batch processing, vector embeddings, similarity search, mismatch guard rules, cost tracking, review API endpoints, and evaluation scripts execute cleanly and pass.
