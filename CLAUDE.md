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
[ ] Phase 4 — Dependency graph
    [x] Step 1 — Graph data models & migration
    [x] Step 2 — Import extractors
    [ ] Step 3 — Graph builder service
    [ ] Step 4 — Wire into Celery
    [ ] Step 5 — GET /repos/{id}/graph endpoint
[ ] Phase 5 — Frontend
[ ] Phase 6 — Deploy

## Session Log
### 2026-05-31 (Phase 4 Step 2)
Phase 4 Step 2 complete. Import extractors built for Python and
JavaScript/TypeScript.

app/graph/extractors/base.py: ImportEdge frozen dataclass with fields
source_file, import_raw, target_module. BaseExtractor abstract base
class with single abstract method extract(file_path, source_code) ->
list[ImportEdge].

app/graph/extractors/python_extractor.py: PythonExtractor using stdlib
ast module. Handles simple imports (import os), dotted imports
(import foo.bar.baz), from imports single and multi-symbol (from foo
import bar, baz → two edges foo.bar and foo.baz), relative imports
(from .relative import x → .relative.x preserving leading dots), star
imports (from foo import *), and parenthesized multi-imports. Never
raises — catches SyntaxError and all parse failures, logs a warning,
and returns partial results or empty list.

app/graph/extractors/javascript_extractor.py: JavaScriptExtractor using
regex-based extraction. Handles named imports (import { bar } from),
default imports (import React from), namespace imports (import * as x
from), dynamic imports (import('./dynamic')), CommonJS require(),
re-exports (export { x } from), and export star (export * from).
target_module is the raw specifier string. One ImportEdge per import
statement, not per symbol. Supports .js, .jsx, .ts, .tsx files.

app/graph/extractors/registry.py: get_extractor(file_path) maps
extensions to cached extractor instances. .py → PythonExtractor,
.js/.jsx/.ts/.tsx → JavaScriptExtractor, all others → None. Instances
are cached — same object returned for repeated calls.

tests/graph/test_extractors.py: Full test coverage across all extractor
types and the registry. Verified: PythonExtractor handles all import
forms and never raises on broken syntax. JavaScriptExtractor handles
all import/export/require forms and returns empty list for files with
no imports. Registry maps all supported extensions correctly and
returns None for unsupported extensions. Extractor instances are
cached.

Full suite: 182 tests green.

### 2026-05-30 (Phase 4 Step 1)
Phase 4 Step 1 complete. Dependency graph data models and Alembic
migration added.

app/models/graph.py: Two new SQLAlchemy ORM models. FileNode with fields
id (UUID PK), repo_id (UUID FK → repositories.id, NOT NULL, CASCADE
DELETE), file_path (str, NOT NULL), language (str, NOT NULL),
import_count (int, default 0), imported_by_count (int, default 0),
created_at (datetime, server_default now). Unique constraint on
(repo_id, file_path). FileDependency with fields id (UUID PK), repo_id
(UUID FK → repositories.id, NOT NULL, CASCADE DELETE), source_file
(str, NOT NULL), target_file (str, NULLABLE — None when import cannot
be resolved to a repo file e.g. third-party packages), import_raw
(str, NOT NULL), created_at (datetime, server_default now). Index on
(repo_id, source_file).

app/models/__init__.py: Both FileNode and FileDependency registered.

alembic/versions/a8e3f1c92d74_add_file_nodes_and_file_dependencies_tables.py:
Migration adds both tables with constraints and index. Verified
upgrade and downgrade both apply cleanly against Postgres.

tests/models/test_graph_models.py: 4 tests — FileNode creation and
query, FileDependency creation and query, cascade delete removes both
FileNode and FileDependency rows when parent Repository is deleted,
unique constraint on (repo_id, file_path) raises IntegrityError on
duplicate insert.

One bug caught during verification: target_file was initially created
NOT NULL. Fixed to NULLABLE before committing — required for Step 3
where unresolved imports (third-party packages like react, lodash)
store None as target_file.

Full suite: 136 tests green.

### 2026-05-30 (Phase 3 Step 6)
Phase 3 Step 6 complete. POST /chat endpoint wiring RAGPipeline into
FastAPI, verified end-to-end with real queries.

app/api/chat.py: POST /chat with module-level RAGPipeline singleton
(avoids reloading the embedding model per request). Validates repo
exists (404) and status is "completed" (400). Converts Citation
dataclasses to CitationResponse Pydantic models. _make_relative_path
normalizes absolute temp clone paths to repo-relative paths using a
regex (_TMP_SEGMENT_RE = re.compile(r"/tmp[a-z0-9_]+/")) that strips
everything up to and including the mkdtemp segment, then conditionally
prepends {repo_name}/ if the remaining path doesn't already start with
it — handles both package files (databases/backends/mysql.py) and
files elsewhere in the repo (databases/tests/test_databases.py).

app/api/schemas.py: added CitationResponse, ChatRequest (with
@field_validator rejecting empty/whitespace questions), ChatResponse.

app/main.py: registered chat_router.

End-to-end verification against https://github.com/encode/databases:
404 on unknown repo_id, 422 on empty question, 400 on unindexed repo,
grounded answer with inline citations and clean relative file paths on
real question, graceful refusal with citations=[] on off-topic question.

Full suite: 132 tests green.

### 2026-05-30 (Phase 3 Step 5)
Phase 3 Step 5 complete. RAG pipeline and LLM client interface built
and verified end-to-end against a real indexed repo.

app/services/llm.py: LLMClient ABC with async generate(system, user,
max_tokens) -> str. OpenAIClient implementation using AsyncOpenAI with
JSON mode (response_format={"type": "json_object"}), lazy client init,
model configurable via LLM_MODEL env var (default gpt-4o-mini).
get_llm_client() factory driven by LLM_PROVIDER env var. Mirrors the
Embedder interface pattern exactly.

app/rag/pipeline.py: RAGPipeline.answer(repo_id, question) async method
running embed -> retrieve -> build context -> LLM -> parse. Sync
embed_query and vector_store.query wrapped in run_in_executor to protect
the event loop; LLM call awaited directly as I/O-bound. Citation
dataclass with file_path, function_name, start_line, end_line,
chunk_type, snippet. _build_context formats numbered context blocks
labeled with file_path:start_line-end_line. _parse_response uses
json.loads only — no regex; out-of-range chunk indices silently dropped;
malformed JSON raises ValueError. Empty retrieval returns graceful
message with citations=[]. System prompt explicitly instructs the model
to use only provided context and say so if insufficient.

Manual verification against https://github.com/encode/databases
(169 chunks, 50 files): 5 questions asked — connection pool, query
execution, transaction handling, URL parsing, and an off-topic sourdough
question. All 4 code questions returned grounded answers with inline
citations mapping to real classes and line ranges. Off-topic question
returned clean refusal with 0 citations and no hallucination.

Note: file_path values in citations are currently absolute temp clone
paths (e.g. C:\Users\...\AppData\Local\Temp\tmpXXX\repo\file.py).
This will be cleaned up to relative paths in Step 6 at the endpoint
layer.

Full suite: 123 tests green.

### 2026-05-29 (Phase 3 Step 4)
Phase 3 Step 4 complete. The full parse → embed → store pipeline is now
wired into the Celery index_repository task and verified end-to-end.

Two bugs were found and fixed in the API layer. First, the IndexRequest
Pydantic schema was missing the force_reindex field; added
force_reindex: bool = False. Second, the POST /repos/index handler was
ignoring force_reindex entirely — when a repo already existed with
status "completed", it returned that stale status immediately without
re-queuing the task. Fixed by adding explicit branching: when
force_reindex=True, the handler now deletes all existing CodeChunk rows
for the repo, drops the Chroma collection via
get_vector_store().drop_collection(), creates a new IndexingJob with
status="pending", queues the Celery task, and returns status="queued".
When force_reindex=False and the repo exists, it returns the existing
job state unchanged.

End-to-end verification against https://github.com/encode/databases:
POST /repos/index with force_reindex=true returned status "queued"
immediately; Celery worker received the task, cloned the repo, loaded
the all-MiniLM-L6-v2 embedding model, parsed and embedded all files;
SSE stream progressed from running→persisting→storing→completed with
progress_pct climbing 50→90→100; pipeline completed in 90 seconds;
169 chunks across 50 files stored in both Postgres code_chunks table
and ChromaDB collection repo_{repo_id}. Full test suite green.

### 2026-05-29 (Phase 3 Step 3)
ChromaDB storage layer complete at app/services/vector_store.py. The
VectorStore class wraps a chromadb.PersistentClient and exposes five
synchronous methods for the Celery worker: get_or_create_collection(repo_id)
returns the named Chroma collection (repo_{repo_id}); add_chunks(repo_id,
chunks, embeddings) stores chunk.id as the Chroma document id, chunk.content
as the document text, and file_path, chunk_type, function_name, start_line,
end_line, and language as metadata (function_name is coerced to "" when None
since ChromaDB metadata values cannot be None); query(repo_id, embedding,
top_k=5) returns a ranked list of dicts with chunk_id, content, metadata, and
distance, guarding against the n_results > count error by clamping to the
collection size and returning [] on an empty collection; drop_collection(repo_id)
deletes the collection and swallows the exception if it doesn't exist;
chunk_count(repo_id) returns the integer count. The module-level
get_vector_store() factory provides the process-wide singleton client for
production callers. Persistence path is ./chroma_data, added to .gitignore.

Beyond the 14-test unit suite, three end-to-end behaviors were verified
manually after a process restart: persistence held across restarts (chunks
added in one process were found in a fresh one pointing at the same
chroma_data directory); a real semantic query ("how does authentication work")
ranked def login above unrelated chunks (def render_button, class
DatabasePool); and repo_id isolation held — querying repo 1 returned no
documents from repo 2's collection. Full suite: 98 tests green.

Next: Step 4 — wire parsing + embedding + storage into the existing Celery
index_repository task (Sonnet 4.6, plan mode).

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