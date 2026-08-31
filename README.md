# AI Image Understanding & Content Matching Engine

Backend system built with Python, FastAPI, PostgreSQL, and pgvector that automatically ingests image libraries using Vision AI, generates semantic embeddings, and pairs images with blog posts using a deterministic Mismatch Guard safety layer.

---

## What the System Does

1. **Structured Vision Ingestion**: Processes images through `bakllava:7b` via Ollama to extract structured Pydantic metadata (`subject`, `category`, `attributes`, `caption`, `confidence`). Images with low confidence (`< 0.70`) are flagged for review rather than blindly accepted.
2. **Asynchronous Background Processing**: Offloads bulk ingestion tasks to background jobs with retry logic, progress tracking (0–100%), and per-call cost tracking.
3. **Semantic Matching Engine**: Maps post content and image captions into a shared 768-dimensional vector space (`nomic-embed-text`) and ranks candidate matches using cosine similarity.
4. **Mismatch Guard Safety Layer**: Evaluates candidate matches against strict business rules before recommending an image:
   - **Category Mismatch**: Rejects candidates of an incorrect animal class (e.g. rejecting a wolf image for a red fox post).
   - **Similarity Threshold**: Rejects candidates with similarity below `0.65`.
   - **Vision Confidence**: Rejects candidates with vision confidence below `0.70`.
5. **"No Confident Match" Fallback**: Safe refusal pattern when no candidate satisfies all guard rules.
6. **Human Review API**: REST endpoints to inspect decision rationales, record reviewer approvals/rejections, and inspect system cost usage.

---

## Architecture Diagram

```text
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

## Evaluation Metrics (PROBE 5)

The evaluation suite (`scripts/eval_precision.py`) measures Top-1 recommendation precision across a hand-labeled dataset of 10 posts covering 5 animal categories (`red_fox`, `wolf`, `dog`, `bear`, `deer`).

```text
=================== EVALUATION RESULTS ===================
Total Evaluated Posts : 10
Correct Top-1 Matches : 7
Top-1 Precision Score : 70.0%
=======================================================
```

### Threshold Defense:
- **Similarity Threshold (0.65)**: Chosen to prevent false positives across related animal families (e.g. wolves vs. domestic dogs) while accepting valid phrasing variations in text embeddings.
- **Vision Confidence Cutoff (0.70)**: Successfully isolates blurry or low-quality source images without excluding clear wildlife photography.

---

## Setup & Execution Guide

### 1. Prerequisites
- **Python 3.11+**
- **Docker & Docker Compose** (for PostgreSQL + pgvector)
- **Ollama** running locally with the required models:
  ```bash
  ollama pull bakllava:7b
  ollama pull nomic-embed-text
  ```

### 2. Environment Setup
Copy the placeholder environment file:
```bash
cp .env.example .env
```

### 3. Start PostgreSQL Database
```bash
docker compose up -d
```

### 4. Run Database Migrations
Apply Alembic migrations to set up schema and pgvector tables:
```bash
alembic upgrade head
```

### 5. Seed Dataset (50 Images)
Populate the database with the initial dataset of 50 images:
```bash
python scripts/seed.py
```

### 6. Run Evaluation Script
Execute the Top-1 Precision evaluation script:
```bash
python scripts/eval_precision.py
```

### 7. Run Application Server
Start the FastAPI server:
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```
Interactive API documentation is available at `http://localhost:8000/docs`.

### 8. Run Automated Test Suite
Run the test suite via pytest:
```bash
python -m pytest
```

---

## API Reference (`/api/v1`)

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/health` | Health check endpoint |
| `POST` | `/api/v1/images/ingest` | Queue image URLs for background vision processing |
| `GET` | `/api/v1/jobs/{id}` | Poll progress and status of background jobs |
| `GET` | `/api/v1/images` | List ingested images filtered by metadata or status |
| `GET` | `/api/v1/images/{id}` | Retrieve image metadata and processing details |
| `POST` | `/api/v1/posts` | Create blog post and generate text embedding |
| `GET` | `/api/v1/posts/{id}/matches` | Find matching images via semantic search and Mismatch Guard |
| `POST` | `/api/v1/suggestions/{id}/approval` | Record human approval or rejection of suggestions |
| `GET` | `/api/v1/costs` | Retrieve per-call AI usage cost logs |

---

## Honest Limitations

1. **Local CPU Inference Latency**: Running vision model inference (`bakllava:7b`) on CPU takes approximately 2–4 seconds per image during initial ingestion. GPU acceleration via Ollama reduces batch processing time significantly.
2. **Linear Vector Ranking at Small Scale**: Candidate ranking performs exact cosine distance matrix calculation over in-database embeddings, which runs instantly for thousands of images but would benefit from pgvector HNSW indexing at scales exceeding 100,000 images.
