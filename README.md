# OmniExtract AI

OmniExtract AI is an enterprise-grade multimodal document ingestion and structured-data extraction microservice. It is designed to process complex business documents—such as invoices, fuel receipts, logistics waybills, and vendor quotes—by integrating high-fidelity document preprocessing, multimodal Large Language Models (LLMs), strict Pydantic validation, and relational persistence.

---

## Current Architecture

OmniExtract AI implements a durable, asynchronous task queue and document parsing architecture built on PostgreSQL:

```
  ┌─────────────────┐
  │ FastAPI Service │
  └────────┬────────┘
           │
           │ 1. POST /documents/upload
           │    - Validates file magic bytes (PDF, PNG, JPEG) & max size limit
           │    - Saves file with secure UUID filename to persistent storage
           │    - Inserts Document & QUEUED ProcessingJob in PostgreSQL
           ▼
  ┌────────────────────────────────────────────────────────┐
  │ PostgreSQL Database (processing_jobs, documents)       │
  └────────┬───────────────────────────────────────────────┘
           │
           │ 2. Polling Worker claims job via SELECT ... FOR UPDATE SKIP LOCKED
           │    - Updates job status to PROCESSING in a short transaction
           │    - Releases database transaction immediately
           ▼
  ┌─────────────────┐
  │ Polling Worker  │
  └────────┬────────┘
           │
           │ 3. Document Parsing (Outside active DB transaction)
           │    - PDF: PyMuPDF extracts text page by page; flags textless PDFs (requires_ocr=True)
           │    - Images (PNG, JPEG): Pillow validates image decoding and inspects dimensions/mode
           │    - Sanitized error handling for corrupted or invalid documents
           ▼
  ┌────────────────────────────────────────────────────────┐
  │ PostgreSQL Database (parsed_documents table)           │
  │    - Persists raw text, per-page structured JSON, and metadata
  │    - Transitions job to COMPLETED (or FAILED on error)
  └────────────────────────────────────────────────────────┘
```

### Core Architecture Concepts Explained

- **What is the Queue?**
  The queue is a durable table in PostgreSQL (`processing_jobs`) where each document upload creates a job record with status `QUEUED`. Instead of processing heavy document extractions synchronously inside the web request, FastAPI quickly saves a job record and returns `202 Accepted` with a `job_id`.

- **What is the Worker?**
  The worker is an independent Python background process (`app/worker.py`) that continuously polls PostgreSQL for `QUEUED` jobs. Once a job is claimed, the worker retrieves document storage metadata, parses the document content without holding a database transaction open, persists structured parsing results, and marks the job `COMPLETED`.

- **How Documents are Parsed:**
  - **PDF Documents:** Parsed page-by-page using PyMuPDF. Page text, character counts, and page boundaries are preserved. If a PDF contains no extractable text, it is cleanly flagged with `requires_ocr = True` for subsequent OCR pipelines without falsely claiming OCR has occurred.
  - **PNG and JPEG Images:** Inspected and fully decoded using Pillow to verify image validity and extract dimensions (`width`, `height`), color mode, and format.
  - **Error Diagnostics:** Corrupted PDFs, broken images, or missing files are safely trapped, and the job transitions to `FAILED` with sanitized diagnostics that avoid leaking server filesystem paths.

- **Why is `SKIP LOCKED` Important?**
  When multiple worker processes run concurrently, `SELECT ... FOR UPDATE SKIP LOCKED` allows each worker to lock and claim a queued job row without blocking or conflicting with other workers. If Worker A locks Job 1, Worker B automatically skips Job 1 and claims Job 2 simultaneously without lock contention or duplicate processing.

---

## Tech Stack

- **Language:** Python 3.11+
- **API Framework:** FastAPI
- **Data Validation & Settings:** Pydantic v2 & Pydantic Settings
- **Database & ORM:** PostgreSQL, SQLAlchemy 2.0 (async), `asyncpg`
- **Database Migrations:** Alembic
- **Document Processing:** PyMuPDF (`pymupdf`), Pillow (`PIL`)
- **Containerization:** Docker & Docker Compose
- **Testing & Quality:** pytest, `httpx`, `aiosqlite`, `ruff`

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

Run tests and linter:
```bash
# Run pytest test suite:
pytest

# Run ruff code linter:
ruff check .
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
    "created_at": "2026-10-11T19:20:00Z"
  }
  ```

- **Query Job Status & Parsed Results:**
  ```bash
  curl -X GET "http://localhost:8000/jobs/3fa85f64-5717-4562-b3fc-2c963f66afa6"
  ```
  *Response (HTTP 200 OK after worker completes):*
  ```json
  {
    "job_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
    "status": "COMPLETED",
    "created_at": "2026-10-11T19:20:00Z",
    "started_at": "2026-10-11T19:20:01Z",
    "completed_at": "2026-10-11T19:20:02Z",
    "error_message": null,
    "parsed_document": {
      "raw_text": "Invoice #1001...",
      "pages": [
        {
          "page_number": 1,
          "text": "Invoice #1001...",
          "char_count": 450
        }
      ],
      "page_count": 1,
      "requires_ocr": false,
      "metadata_json": {
        "format": "PDF",
        "page_count": 1,
        "title": null,
        "author": null
      }
    }
  }
  ```

- **Swagger Documentation:** `http://localhost:8000/docs`
- **OpenAPI Schema:** `http://localhost:8000/openapi.json`

---

## License

Distributed under the [MIT License](LICENSE).
