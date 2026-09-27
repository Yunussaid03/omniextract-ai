# OmniExtract AI

OmniExtract AI is an enterprise-grade multimodal document ingestion and structured-data extraction microservice. It is designed to process complex business documents—such as invoices, fuel receipts, logistics waybills, and vendor quotes—by integrating high-fidelity document preprocessing, multimodal Large Language Models (LLMs), strict Pydantic validation, and relational persistence.

---

## Current Architecture

OmniExtract AI implements a durable, asynchronous task queue architecture built directly on PostgreSQL:

```
  ┌─────────────────┐
  │ FastAPI Service │
  └────────┬────────┘
           │
           │ 1. POST /documents/upload -> Inserts QUEUED job & returns HTTP 202 Accepted
           ▼
  ┌────────────────────────────────────────────────────────┐
  │ PostgreSQL Database (processing_jobs table)            │
  └────────┬───────────────────────────────────────────────┘
           │
           │ 2. Worker polls & claims job via SELECT ... FOR UPDATE SKIP LOCKED
           ▼
  ┌─────────────────┐
  │ Polling Worker  │  <-- Updates status to PROCESSING in a short transaction
  └─────────────────┘
```

### Core Architecture Concepts Explained

- **What is the Queue?**
  The queue is a durable table in PostgreSQL (`processing_jobs`) where each document upload creates a job record with status `QUEUED`. Instead of processing heavy document extractions synchronously inside the web request, FastAPI quickly saves a job record and returns `202 Accepted` with a `job_id`.

- **What is the Worker?**
  The worker is an independent Python background process (`app/worker.py`) that continuously polls PostgreSQL for `QUEUED` jobs. Once a job is found, the worker updates its status to `PROCESSING` and records its `started_at` timestamp before proceeding with document tasks.

- **Why PostgreSQL as the Queue?**
  Using PostgreSQL as the job queue eliminates the complexity of introducing external message brokers (like Redis, RabbitMQ, or Celery) during early architecture phases. It provides ACID guarantees, transaction safety, simplified operations, and zero extra infrastructure overhead.

- **Why is `SKIP LOCKED` Important?**
  When multiple worker processes run concurrently, `SELECT ... FOR UPDATE SKIP LOCKED` allows each worker to lock and claim a queued job row without blocking or conflicting with other workers. If Worker A locks Job 1, Worker B automatically skips Job 1 and claims Job 2 simultaneously without lock contention or duplicate processing.

---

## Tech Stack

- **Language:** Python 3.11+
- **API Framework:** FastAPI
- **Data Validation & Settings:** Pydantic v2 & Pydantic Settings
- **Database & ORM:** PostgreSQL, SQLAlchemy 2.0 (async), `asyncpg`
- **Database Migrations:** Alembic
- **Document Processing:** PyMuPDF (`fitz`), Pillow (`PIL`)
- **Containerization:** Docker & Docker Compose
- **Testing:** pytest, `httpx`, `aiosqlite`

---

## Local Development Setup

### 1. Clone Repository
```bash
git clone https://github.com/Yunussaid03/omniextract-ai.git
cd omniextract-ai
```

### 2. Environment Configuration
Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```

### 3. Running with Virtual Environment (Local Python)

Create and activate a virtual environment:
```bash
python -m venv .venv
# On Linux/macOS:
source .venv/bin/activate
# On Windows:
.venv\Scripts\activate
```

Install dependencies:
```bash
pip install -e ".[dev]"
```

Run tests:
```bash
pytest
```

Run database migrations:
```bash
alembic upgrade head
```

Run local API server:
```bash
uvicorn app.main:app --reload --port 8000
```

Run standalone background worker:
```bash
python -m app.worker
# Or run a single pass and exit:
python -m app.worker --once
```

### 4. Endpoints & API Usage

- **Upload Document (Initiate Job):**
  ```bash
  curl -X POST "http://localhost:8000/documents/upload" \
    -F "file=@sample_invoice.pdf"
  ```
  *Response (HTTP 202 Accepted):*
  ```json
  {
    "job_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
    "status": "QUEUED",
    "created_at": "2026-09-27T14:20:00Z"
  }
  ```

- **Query Job Status:**
  ```bash
  curl -X GET "http://localhost:8000/jobs/3fa85f64-5717-4562-b3fc-2c963f66afa6"
  ```
  *Response (HTTP 200 OK):*
  ```json
  {
    "job_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
    "status": "PROCESSING",
    "created_at": "2026-09-27T14:20:00Z",
    "started_at": "2026-09-27T14:20:01Z"
  }
  ```

- **Swagger Documentation:** `http://localhost:8000/docs`
- **OpenAPI Schema:** `http://localhost:8000/openapi.json`

---

## License

Distributed under the [MIT License](LICENSE).
