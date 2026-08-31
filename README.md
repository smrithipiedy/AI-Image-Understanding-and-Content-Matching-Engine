# FlyRank Capstone — AI Image Understanding & Content Matching Engine

An asynchronous backend system that ingests an image library using Vision AI (`bakllava:7b`), extracts structured metadata, generates text & image embeddings (`nomic-embed-text`), and matches images to blog posts using semantic similarity with a **production-grade Mismatch Guard safety layer**.

---

## 🔑 Key Features & Production Safety

1. **Structured Vision Pipeline**: Processes images through `bakllava:7b` to extract structured JSON metadata (`subject`, `category`, `attributes`, `caption`, `confidence`). Enforces Pydantic schema validation. Low-confidence classifications (`< 0.70`) are flagged for review rather than accepted.
2. **Background Batch Processing**: Asynchronous job engine handling ingestion, progress tracking (0–100%), error logging, exponential retries, and per-call cost tracking (`$0.00` local Ollama usage).
3. **Semantic Matching Engine**: Vector representations calculated for post content and image captions into a shared 768-dimensional space (`nomic-embed-text`), ranked using cosine similarity.
4. **Mismatch Guard Safety Layer**: Evaluates candidate matches against strict business safety rules:
   - **Category Mismatch**: Rejects wolf images for red fox posts (`"Animal category mismatch: expected red_fox, detected wolf"`).
   - **Similarity Threshold**: Rejects candidates with cosine similarity below `0.75`.
   - **Vision Confidence**: Rejects candidates with vision confidence below `0.70`.
5. **"No Confident Match" Fallback**: Refuses uncertain pairings rather than guessing.
6. **Human Review API**: REST endpoints to inspect decision rationale and record reviewer approvals/rejections.
7. **Evaluation Suite**: Includes labeled dataset script (`scripts/eval_precision.py`) measuring Top-1 Precision.

---

## 🏗️ Architecture Overview

```
                                 [ IMAGE CORPUS ]
                                         │
                                   (Batch Job)
                                         ▼
                            [ Vision Model (Bakllava) ]
                                         │
                                (Schema Validation)
                                         ▼
                       ┌──────────────────────────────────┐
                       │      Image Metadata & Tags       │
                       └────────────────┬─────────────────┘
                                        │
                             Embed(Caption & Tags)
                                        ▼
                              [ Image Vector Index ]
                                        │
                                        │ (Cosine Similarity)
[ Blog Post ] ────► Embed(Post) ────────┼────────► [ Candidate Ranking ]
                                        │                 │
                                                          ▼
                                                 [ Mismatch Guard ]
                                              (Category/Score Check)
                                                          │
                                     ┌────────────────────┴────────────────────┐
                                     ▼                                         ▼
                             [ MATCH APPROVED ]                      [ NO CONFIDENT MATCH ]
                             Suggested Image +                        Explanation & Guard
                            Human Explanation                             Reasons
                                     │                                         │
                                     └────────────────────┬────────────────────┘
                                                          ▼
                                                  [ Review API ]
                                                (Approve / Reject)
```

---

## 📊 Evaluation Results (PROBE 5)

The system is evaluated using `scripts/eval_precision.py` against a hand-labeled dataset of 10 posts spanning 5 animal categories (`red_fox`, `wolf`, `dog`, `bear`, `deer`).

```text
=================== EVALUATION RESULTS ===================
Total Evaluated Posts : 10
Correct Top-1 Matches : 9
Top-1 Precision Score : 90.0%
=======================================================
```

### Threshold Selection & Defense:
- **Similarity Threshold**: `0.75` was selected based on evaluation tuning. Thresholds below `0.70` caused false-positive matches across canine boundaries (wolf/dog), while thresholds above `0.85` resulted in false rejections of valid red fox variations.
- **Vision Confidence Cutoff**: `0.70` successfully flags blurry or ambiguous input images without rejecting valid wild animal photos.

---

## 🚀 Quickstart & Setup Guide

### 1. Prerequisites
- **Python 3.11+**
- **Docker & PostgreSQL** (or local SQLite fallback)
- **Ollama** running locally with `bakllava:7b` and `nomic-embed-text`:
  ```bash
  ollama pull bakllava:7b
  ollama pull nomic-embed-text
  ```

### 2. Environment Configuration
Copy environment file:
```bash
cp .env.example .env
```

### 3. Database Migration & Table Initialization
Tables are automatically initialized on application startup via FastAPI lifespan hook.

### 4. Running Seed & Ingestion Script
To populate database with 50 images across 5 animal categories:
```bash
python scripts/seed.py
```

### 5. Running evaluation script
To measure Top-1 precision on labeled dataset:
```bash
python scripts/eval_precision.py
```

### 6. Starting FastAPI Application Server
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```
API Documentation will be available at `http://localhost:8000/docs`.

### 7. Running Test Suite
```bash
python -m pytest
```

---

## 🌐 Key API Endpoints (`/api/v1`)

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/health` | Service health status |
| `POST` | `/api/v1/images/ingest` | Ingest image URLs & queue background job |
| `GET` | `/api/v1/jobs/{id}` | Check job progress and status |
| `GET` | `/api/v1/images` | List ingested images with metadata & status filters |
| `GET` | `/api/v1/images/{id}` | Fetch image details |
| `POST` | `/api/v1/posts` | Create post and generate text embedding |
| `GET` | `/api/v1/posts/{id}/matches` | Match post to images through Mismatch Guard |
| `POST` | `/api/v1/suggestions/{id}/approval` | Record human review decision |
| `GET` | `/api/v1/costs` | View per-call AI usage cost logs |

---

## ⚠️ Honest Limitations Note

1. **Local Vision Inference Latency**: Running vision model (`bakllava:7b`) on CPU can take 2–4 seconds per image during initial batch processing. Using GPU acceleration via Ollama speeds up batch ingestion significantly.
2. **Corpus Scale**: The vector search currently performs exact cosine distance matrix calculation across in-database embeddings, which is optimal and instant for corpus sizes up to thousands of images (~50 in standard dataset), but would benefit from `pgvector` HNSW indexes at scales exceeding 100,000 images.
