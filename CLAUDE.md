# ContextCode — CLAUDE.md

## Project Summary
AI codebase onboarding tool. Users paste a public GitHub URL, we index it 
using AST parsing, let them chat with the codebase via RAG, and visualize 
file dependencies with danger zone analysis.

## Stack
- Backend: FastAPI, Python 3.11, LangChain, Tree-sitter, ChromaDB, PostgreSQL
- Frontend: Next.js 14 (App Router), TypeScript, Tailwind, React Flow
- Deploy: Vercel (frontend), Railway (backend)

## Rules — follow these every session, no exceptions
- Never push to main directly
- Always write tests alongside new services
- Backend lives in /backend, frontend in /frontend
- Use async/await throughout FastAPI
- All endpoints must have Pydantic request/response models
- SSE for progress streaming, not polling
- Supported languages MVP: Python, JavaScript, TypeScript only
- Skip: node_modules, dist, build, .git, binaries during indexing
- Max repo size: 10,000 files, 500MB
- Embeddings go behind an Embedder interface (app/services/embeddings.py)
  with two implementations: local sentence-transformers (all-MiniLM-L6-v2,
  384 dims) as the DEFAULT, and OpenAI as a swappable alternative. Code
  must never call an embedding provider directly — only through the interface.
- CPU-bound work (tree-sitter parsing, local embedding generation) must NOT
  run in async endpoints. Use background tasks / threadpool to keep the
  event loop and SSE stream responsive.
- Indexing runs as a background job that writes progress to the IndexingJob
  record. The SSE endpoint reads job state only — it does not perform the
  work itself.
- Celery worker on Windows local dev must use --pool=solo flag due to prefork
  incompatibility with Windows. Production deployment on Railway runs Linux
  containers, where default prefork works.
- Chunking granularity: function-level and class-level chunks. Module-level
  code (imports, top-level constants, module docstrings) becomes a single
  chunk per file with chunk_type='module'.
- ChromaDB: one collection per repo, named `repo_{repo_id}`. Re-indexing
  drops and recreates the collection.
- LLM generation goes behind an LLMClient interface (app/services/llm.py)
  with OpenAI as the default implementation. Code must never call an LLM
  provider directly — only through the interface.
- POST /repos/index on an existing URL returns the existing repo by
  default; pass `force_reindex=true` to drop chunks and re-run.
- Parsing and embedding are CPU-bound — they run inside the Celery task,
  never in an async endpoint.

## Local Development — Startup
Run these in order each session (Docker containers don't auto-start after reboot):

1. **Docker Desktop** — ensure it is running before anything else
2. **Postgres + Redis** — from repo root:
   ```
   docker compose up -d
   ```
3. **Celery worker** — from `/backend` (Windows requires `--pool=solo`):
   ```
   celery -A app.workers.celery_app worker --pool=solo --loglevel=info
   ```
4. **FastAPI server** — from `/backend`:
   ```
   uvicorn app.main:app --reload
   ```

## What we are NOT building
- Autonomous coding agents
- Code generation or copilot features
- GitHub PR automation
- Multi-user auth
- LangGraph or multi-agent systems

## API Endpoints
- POST /repos/index → {repo_id, status}
- GET /repos/{id}/status → SSE stream of progress
- POST /chat → {answer, citations}
- GET /repos/{id}/graph → dependency graph JSON

## Data Models
- Repository: id, url, name, status, created_at, file_count
- CodeChunk: id, repo_id, file_path, chunk_type, function_name, 
  start_line, end_line, content, language
- IndexingJob: id, repo_id, status, progress_pct, error_message, 
  created_at, updated_at

## Folder Structure
backend/
├── app/
│   ├── api/
│   ├── services/
│   ├── parsers/
│   ├── rag/
│   ├── graph/
│   ├── models/
│   ├── workers/
│   └── utils/
├── tests/
├── Dockerfile
└── requirements.txt

frontend/
├── app/
├── components/
├── hooks/
├── lib/
├── types/
└── utils/

## Current Status
[x] Phase 1 — Scaffold
[x] Phase 2 — Ingestion pipeline
[ ] Phase 3 — RAG chat
[ ] Phase 4 — Dependency graph
[ ] Phase 5 — Frontend
[ ] Phase 6 — Deploy

## Session Log
<!-- Update this after every session with what was completed -->

### 2026-05-28
Phase 2 — Ingestion pipeline complete. Full local dev stack established:
docker-compose with Postgres + Redis, SQLAlchemy ORM models (Repository,
IndexingJob) with async + sync sessions, Alembic async migrations. Celery
worker wired to Redis with index_repository task (shallow clone, file
walking with binary/skip-dir detection, size limits, progress writes to
IndexingJob). POST /repos/index endpoint with Pydantic request/response
models; duplicate-URL handled by returning existing repo. GET
/repos/{id}/status SSE endpoint streams job progress from DB at 1s
intervals. pytest suite: 29 tests passing against SQLite in-memory via
aiosqlite — no running Postgres or Celery required. Next: Phase 3 — RAG
chat (AST parsing, Embedder interface, ChromaDB storage, POST /chat).

### 2026-05-27
Phase 2 Step 4 complete. Implemented IngestionService (URL validation,
shallow clone, file walking with binary/skip-dir detection, size limits
enforced: 10,000 files, 500MB) and the real index_repository Celery task
using a sync DB session to write progress to IndexingJob. All unit tests
passing, committed. Next: Step 5 — POST /repos/index and GET /repos/{id}/status
SSE endpoints.

### 2026-05-26
Phase 1 scaffold complete and verified. /backend: FastAPI app with
GET /health (test passing), all app/ subpackages with __init__.py,
requirements.txt (18 packages), pytest.ini, Dockerfile, .gitignore.
/frontend: Next.js 14.2.35 with TypeScript strict, Tailwind, ESLint,
App Router; custom dirs (components/, hooks/, lib/, types/, utils/).
Root-level monorepo .gitignore added. Pushed to GitHub.

Phase 1 scaffold complete and verified — backend boots, /health returns
200 OK, /docs works, all committed and pushed to GitHub. Next up: Phase 2
ingestion pipeline.