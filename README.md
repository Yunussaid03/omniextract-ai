# OmniExtract AI

OmniExtract AI is an enterprise-grade multimodal document ingestion and structured-data extraction microservice. It is designed to process complex business documents—such as invoices, fuel receipts, logistics waybills, and vendor quotes—by integrating high-fidelity document preprocessing, multimodal Large Language Models (LLMs), strict Pydantic validation, and relational persistence.

---

## Current Status

> [!NOTE]
> This repository is currently in its **Initial Foundation Phase**.

The present codebase establishes the project foundation, environment configuration, database session setup, containerization, and test scaffolding. Application domain models, asynchronous background workers, and AI extraction pipelines have not yet been implemented and will be designed systematically.

---

## Planned Architecture

When fully realized, OmniExtract AI will feature an end-to-end extraction and validation pipeline:

```
[ Incoming API Request / Document ]
               │
               ▼
   ┌──────────────────────┐
   │   FastAPI Service    │
   └───────────┬──────────┘
               │
               ▼
   ┌──────────────────────┐
   │ Document Preprocess  │  <-- PyMuPDF / Pillow page rendering & normalization
   └───────────┬──────────┘
               │
               ▼
   ┌──────────────────────┐
   │  Multimodal LLM      │  <-- Vision & document representations
   └───────────┬──────────┘
               │
               ▼
   ┌──────────────────────┐
   │  Pydantic Validation │  <-- Strict schema parsing & structured output
   └───────────┬──────────┘
               │
               ▼
   ┌──────────────────────┐
   │ Business Rules Check │  <-- Deterministic financial/business validation
   └───────────┬──────────┘
               │
               ▼
   ┌──────────────────────┐
   │ PostgreSQL Database  │  <-- Persistence of extraction, state, & audit logs
   └──────────────────────┘
```

Future capabilities will also include:
- **Asynchronous processing & message queues**
- **Idempotent processing & retries**
- **Auditability & Observability (tracing, metrics, structured logs)**

---

## Tech Stack

- **Language:** Python 3.11+
- **API Framework:** FastAPI
- **Data Validation & Settings:** Pydantic v2 & Pydantic Settings
- **Database & ORM:** PostgreSQL, SQLAlchemy 2.0 (async), `asyncpg`
- **Database Migrations:** Alembic
- **Document Processing:** PyMuPDF (`fitz`), Pillow (`PIL`)
- **Containerization:** Docker & Docker Compose
- **Testing:** pytest, `httpx`

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

Run local API server:
```bash
uvicorn app.main:app --reload --port 8000
```

### 4. Running with Docker Compose

Start the API and PostgreSQL containers:
```bash
docker compose up --build
```

Access services:
- **API Health Check:** `http://localhost:8000/health`
- **Swagger Documentation:** `http://localhost:8000/docs`
- **OpenAPI Schema:** `http://localhost:8000/openapi.json`
- **PostgreSQL Database:** `localhost:5432`

---

## Architecture Decision Log

Major architectural decisions will be formally evaluated and logged prior to implementation. Upcoming design decisions include:

1. **Synchronous vs. Asynchronous Processing Strategy**
2. **Task Queue & Worker Mechanism** (e.g. Celery / ARQ / Redis / RabbitMQ)
3. **Document Object Storage Architecture** (e.g. S3 / MinIO / Local Blob)
4. **Database Domain Model & Schema Design**
5. **Extraction Schemas & Multimodal Prompt Engineering**
6. **Business & Financial Validation Strategy**
7. **Retry Policies & Idempotency Controls**
8. **Observability, Tracing, and Logging Standards**

---

## License

Distributed under the [MIT License](LICENSE).
