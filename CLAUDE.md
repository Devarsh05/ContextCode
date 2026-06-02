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
- Git commits must not include "Co-Authored-By: Claude" trailers, 
  "Generated with Claude Code" footers, or any AI attribution. Use
  plain commit messages with only the technical description.
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
- Chunking granularity: function-level and class-level chunks. The
  module chunk contains imports, top-level constants, module
  docstrings, and any other top-level statements that are NOT inside
  a function or class. Module chunks must not overlap function/class
  chunk line ranges. Skip the module chunk entirely if the file has
  no non-class/non-function top-level content. chunk_type values are
  strictly 'function', 'class', or 'module' — no other values.
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
[x] Phase 3 — RAG chat
    [x] Step 1 — Embedder interface
    [x] Step 2 — Tree-sitter parsers
    [x] Step 3 — ChromaDB storage
    [x] Step 4 — Wire parsing+embedding into Celery
    [x] Step 5 — RAG pipeline + LLM client
    [x] Step 6 — POST /chat endpoint
[x] Phase 4 — Dependency graph
    [x] Step 1 — Graph data models & migration
    [x] Step 2 — Import extractors
    [x] Step 3 — Graph builder service
    [x] Step 4 — Wire into Celery
    [x] Step 5 — GET /repos/{id}/graph endpoint
[ ] Phase 5 — Frontend
    [x] Step 1 — Design foundation & app shell
    [x] Step 2 — Data layer (typed API client, query hooks, SSE)
    [x] Step 3 — Landing page (hero + wired GitHub-URL form)
    [x] Step 4 — Indexing progress (stepper + SSE, retry on failure)
    [x] Step 5 — Chat tab (composer, bubbles, expandable citations)
    [x] Step 6 — Dependency graph tab (React Flow + dagre, danger zones)
[ ] Phase 6 — Deploy

## Session Log
Full session history lives in docs/SESSION_LOG.md. Read it if you need
context on prior decisions or implementation details.