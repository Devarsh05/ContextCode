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
[ ] Phase 3 — RAG chat
[ ] Phase 4 — Dependency graph
[ ] Phase 5 — Frontend
[ ] Phase 6 — Deploy

## Session Log
<!-- Update this after every session with what was completed -->
### 2026-05-29 (Phase 3 Step 2)
Tree-sitter AST parsers complete and hardened at app/parsers/. The
layer turns raw source files into ParsedChunk objects (a frozen dataclass
with file_path, chunk_type, function_name, start_line, end_line, content,
language) for downstream embedding and RAG retrieval.

base.py defines the BaseParser ABC and the shared TreeSitterParser, which
lazily builds a tree-sitter Language/Parser per grammar and walks the
root's named children. Three concrete parsers ship: PythonParser handles
function_definition, class_definition, and decorated_definition (decorator
lines included in the chunk). JavaScriptParser handles function_declaration,
class_declaration, arrow/function assigned to a single const/let
(lexical_declaration unwrap), and export_statement wrapping. TypeScriptParser
subclasses JS and selects the tsx vs typescript grammar by file extension;
interface_declaration and type_alias_declaration get no dedicated chunk and
fall through to the module chunk so type definitions stay RAG-searchable.
registry.py maps extensions to languages (.py, .js/.jsx, .ts/.tsx) and
caches parser instances; both functions return None for unsupported types.

Chunk types are strictly function, class, and module. Function chunks cover
one top-level function each (including arrow functions assigned to const in
JS/TS); class chunks cover the whole class body with methods kept inside;
the module chunk per contiguous run of top-level statements collects imports,
constants, module docstrings, and anything else not inside a function or
class. Empty and whitespace-only files produce zero chunks. Parsing is
error-tolerant: parse() never raises, logs a warning on syntax errors, and
returns the best-effort partial chunks tree-sitter was able to extract.

Two bugs were caught and fixed during the session through test-driven
debugging. First, module chunk content was being assembled by joining
top-level node texts with "\n" instead of slicing the original source bytes
by byte range; this dropped blank lines between statements, breaking the
substring invariant. The root cause was in the shared base.py helper and
affected all three parsers identically, so it was fixed there. Second,
module chunks were taking a first-to-last byte slice across the entire
file's module-level nodes at once; when module nodes were non-contiguous
(e.g. imports at the top and a TypeVar assignment after several class
definitions), the slice spanned the intervening class bodies, causing the
module chunk's line range to overlap with class and function chunks. Fixed
by switching parse() to a streaming-flush approach: each contiguous run of
module-level nodes is flushed as its own chunk when a function/class node
is encountered, so module chunks fill only the gaps between function/class
definitions.

Two property invariants are now enforced by tests across all three parsers:
the substring invariant (chunk.content is always a verbatim byte-range slice
of the original source) and the no-overlap invariant (module chunk line
ranges never intersect function/class chunk line ranges). Full suite: 84
tests green.

Next: Step 3 — ChromaDB storage layer at app/services/vector_store.py
(Sonnet 4.6, auto mode).

### 2026-05-28 (Phase 3 Step 2)
Tree-sitter AST parsers complete at app/parsers/. base.py defines the
ParsedChunk frozen dataclass (CodeChunk fields minus id/repo_id, 1-indexed
lines), the BaseParser ABC, and a shared TreeSitterParser that lazily builds
the Language/Parser per grammar and walks the root's named children,
classifying each into function/class/module chunks. PythonParser
(function_definition, class_definition, decorated_definition unwrap),
JavaScriptParser (function_declaration, class_declaration, arrow/function
assigned to a single const/let via lexical_declaration, export_statement
unwrap), TypeScriptParser (subclasses JS; picks tsx vs typescript grammar by
file extension; interfaces/type aliases get no dedicated chunk and instead
fall into the module chunk so they stay RAG-searchable). registry.py maps
extensions→language (.py/.js/.jsx/.ts/.tsx) and caches parser instances;
returns None for unsupported. Parsing is error-tolerant: parse() never raises,
logs a warning on syntax errors, and returns best-effort chunks. Module chunk
= top-level nodes that aren't a function/class, joined by newline; empty/blank
files yield zero chunks (no empty module chunk). 29 new tests in
tests/parsers/ (python, javascript, typescript, registry, edge cases incl.
syntax-error files); full suite 78 green. Added tree-sitter-typescript to
requirements.txt (was missing). Note: the CodeChunk SQLAlchemy ORM model still
does not exist — parsers emit plain ParsedChunk; the caller maps it later.
Next: Step 3 — ChromaDB storage (one collection per repo `repo_{repo_id}`),
the CodeChunk ORM model, and wiring parse→embed→store into the
index_repository Celery task.

### 2026-05-28 (Phase 3 Step 1)
Embedder interface complete. app/services/embeddings.py with abstract
Embedder base + LocalEmbedder (sentence-transformers all-MiniLM-L6-v2,
384 dims, default) + OpenAIEmbedder (text-embedding-3-small, swappable
via EMBEDDING_PROVIDER env var). Lazy model loading, batch support,
sync interface for Celery worker. Factory get_embedder() reads
EMBEDDING_PROVIDER env var. 9 new tests in tests/services/test_embeddings.py,
all 49 tests green.

Also fixed test infrastructure: pytest-asyncio 1.4.0 strict-mode break
from dependency upgrade resolved by converting async fixtures in
conftest.py to @pytest_asyncio.fixture and setting asyncio_mode=auto.
Coverage artifacts (.coverage, htmlcov/) added to .gitignore. VS Code
interpreter pinned to backend/.venv via .vscode/settings.json.

Next: Step 2 — Tree-sitter AST parsers for Python/JS/TS at app/parsers/
(Opus 4.7, plan mode, new session).

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