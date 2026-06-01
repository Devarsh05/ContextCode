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
[ ] Phase 6 — Deploy

## Session Log
### 2026-06-01 (Phase 5 Step 2 — Data layer)
Built the frontend data layer — no UI. Fully typed against the generated
OpenAPI types in frontend/types/api.d.ts; no request/response shapes are
hand-written.

frontend/lib/api/client.ts: apiFetch<T>(path, init) reads API_BASE_URL from
NEXT_PUBLIC_API_BASE_URL (default http://localhost:8000, trailing slash
stripped; exported so the SSE hook reuses it), sets JSON Content-Type/Accept
headers (merging caller headers), parses and returns the typed body on 2xx
(204/empty → undefined), and throws ApiError(status, statusText, detail) on
non-2xx. detail is the best-effort-parsed JSON body (falls back to raw text,
never throws while parsing the error body).

frontend/lib/api/types.ts: thin aliases re-exporting components["schemas"][...]
(IndexRequest/Response, ChatRequest/Response, CitationResponse, Graph*).
frontend/lib/api/{repos,chat,graph}.ts: indexRepo(url, forceReindex=false) →
POST /repos/index (maps url→repo_url), postChat(req) → POST /chat,
getGraph(repoId, resolvedOnly=false) → GET /repos/{id}/graph?resolved_only=
(URLSearchParams).

TanStack Query v5 installed. frontend/components/providers.tsx: QueryClient
created once via useState and wrapped in QueryClientProvider INSIDE the existing
next-themes ThemeProvider (staleTime 30s, retry 1, refetchOnWindowFocus false).
Replaces the Step 1 TODO placeholder.

Hooks (frontend/hooks/): useIndexRepo() and useChat() (useMutation),
useGraph(repoId, resolvedOnly) (useQuery, key ["graph", repoId, resolvedOnly],
enabled when repoId truthy). useIndexingStatus(repoId) is a custom EventSource
hook returning { status, progressPct, message, error, done }. It maps the
backend SSE frame (status / progress_pct / current_stage / error_message, or a
top-level error) — the stream is `unknown` in api.d.ts so a local
IndexingStatusEvent type is declared in that one file. Treats BOTH "completed"
and "failed" as terminal (verified against backend/app/api/repos.py), and
closes the connection on terminal status, on a server error payload, on a
transport error (onerror), and on unmount/ repoId change (via a ref, no state
update after teardown).

Tests (Vitest 4 + RTL + jsdom): added frontend/vitest.config.ts (jsdom, react
plugin, setupFiles, @/ alias → __dirname), vitest.setup.ts (jest-dom matchers),
and "test"/"test:run" scripts. Test files import vitest symbols explicitly (no
globals) so tsconfig is untouched. lib/api/__tests__/client.test.ts covers the
2xx parse path, the non-2xx ApiError path with parsed JSON detail, and the
non-JSON error body falling back to raw text. hooks/__tests__/
use-indexing-status.test.ts uses a fake EventSource (records instances + close
spy) to assert: no connection when repoId is null, a running frame maps to the
exposed shape, a completed frame sets done + closes, a server error payload
sets error + done + closes, a transport error closes, and unmount closes
(cleanup).

Verification: tsc --noEmit clean (TS strict), npm run test:run → 9 passed,
next lint clean, next build green (data layer tree-shaken — routes still static,
no bundle change since hooks aren't imported yet).

Next: Phase 5 Step 3 — wire these hooks into the feature UI (index form +
progress, chat, graph).

### 2026-06-01 (Phase 5 Step 1 — Design foundation & app shell)
Phase 5 (Frontend) started. Established the design system and app shell only —
no feature data, no API calls (React Query provider lands next step).

Design direction "Indigo Slate": dark-mode-first, minimal, Linear/Vercel
developer-tool polish. Single electric-indigo (#6366F1) accent on a refined
near-black slate base (#0B0D11); no gradients. Kept the already-installed
Geist Sans + Geist Mono (Geist Mono for code/paths/citations) over swapping to
Inter. Decided via the ui-ux-pro-max tooling + two user choices (accent:
Electric Indigo; base: Refined slate).

Design tokens — single source of truth: frontend/app/globals.css, as shadcn-
style HSL CSS variables under .dark (canonical) + a light :root fallback so
next-themes can toggle. frontend/tailwind.config.ts only references them via
hsl(var(--token)) and never hardcodes colors; it also maps two extra semantic
tokens beyond shadcn defaults — success (emerald, "indexed/completed") and
warning (amber, graph danger zones) — exposed as bg-success/text-warning etc.
Radius --radius: 0.625rem (10px); fontFamily.sans/mono wired to the Geist vars.
frontend/DESIGN.md documents the palette, type/spacing scale, and points to
globals.css as canonical.

shadcn/ui set up non-interactively: pre-created frontend/components.json
(new-york, cssVariables, baseColor slate, @/* aliases) and frontend/lib/utils.ts
(cn helper), then added 12 base components into frontend/components/ui/: button,
input, card, badge, skeleton, sonner, tooltip, scroll-area, tabs, slider,
switch, dropdown-menu. Shadcn MCP server (.mcp.json) used to resolve the add
command.

App shell: frontend/components/providers.tsx (next-themes ThemeProvider,
attribute=class, defaultTheme=dark, enableSystem=false; marked TODO where the
Query provider goes next step). frontend/components/top-nav.tsx (minimal sticky
nav: ContextCode wordmark with indigo Boxes mark + theme toggle, hairline
border, backdrop blur). frontend/components/theme-toggle.tsx (dropdown + lucide
sun/moon). frontend/app/layout.tsx rewritten: ContextCode metadata, <html
className="dark" suppressHydrationWarning>, Geist localFont kept, wraps
Providers + TopNav + <main> + sonner Toaster.

Route skeleton (stubbed, no data): app/page.tsx (landing — eyebrow, big
headline with indigo emphasis, disabled URL input + indigo CTA, 3 benefit
cards), app/repo/[id]/page.tsx (workspace — reads params.id into a mono Badge,
Tabs Chat/Graph each with a dashed empty-state Card), app/not-found.tsx (404
boundary), app/error.tsx ("use client" error boundary with reset()).

No unit tests this step — static presentational shell with no business logic
(only the trivial shadcn cn() helper). Deliberate per the "logic-heavy code"
rule. Verification: tsc --noEmit clean (TS strict), next lint clean, next build
green (5 routes), dev server booted and rendered via Playwright — landing and
/repo/[id] render correctly in dark indigo, tabs switch, zero console errors/
hydration warnings.

Next: Phase 5 Step 2 — React Query provider + wire real data (index, SSE
status, chat, graph).

### 2026-05-31 (SSE EventSource compatibility verified)
Verified GET /repos/{id}/status is compatible with the browser EventSource
API. No code fix was needed — the endpoint already meets the contract:
- content-type text/event-stream (sse_starlette sets
  "text/event-stream; charset=utf-8"; EventSource matches the MIME essence
  and ignores params).
- GET-only: the route is registered with @router.get exclusively; other
  methods get 405.
- No custom request headers required: repo_status's signature is only
  repo_id (path param, in the URL) and the db dependency — no Header(...)
  params, which matters because EventSource cannot set custom headers.
- Proper framing: sse_starlette 3.4.4 encodes each event as
  `data: {json}\r\n\r\n` (confirmed via ServerSentEvent.encode()); CRLF is
  valid per the WHATWG SSE spec and accepted by browsers.

tests/test_repos_api.py: added two tests. test_status_sse_is_browser_
eventsource_compatible streams the raw response, asserts content-type
startswith text/event-stream, and regex-matches a `data: {...}` line
terminated by a blank line (\r?\n\r?\n) on the raw bytes; it sends no
custom headers. test_status_sse_is_get_only asserts POST to the status
path returns 405. The existing test_status_sse_streams_completed_event
(content-type + parsed event) is retained.

Full suite: 218 tests green.

### 2026-05-31 (Frontend API types from OpenAPI)
Set up generation of TypeScript types from the FastAPI OpenAPI schema so the
frontend is typed against the real backend contract instead of hand-written
types.

frontend/package.json: added openapi-typescript ^7.13.0 as a devDependency
and a "gen:types" script:
`openapi-typescript http://localhost:8000/openapi.json -o types/api.d.ts`.
It reads the running backend's /openapi.json (FastAPI serves it
automatically; uvicorn dev runs on :8000) and overwrites types/api.d.ts.

frontend/types/api.d.ts: generated (not hand-written). Emits paths,
components["schemas"], and operations for the whole API — IndexRequest/
Response, ChatRequest/Response, CitationResponse, GraphResponse/
GraphNodeResponse/GraphEdgeResponse, etc. Verified the file typechecks and
the whole frontend project passes tsc --noEmit. Consumed via the existing
@/* path alias, e.g.
`import type { components } from "@/types/api"` →
`components["schemas"]["GraphResponse"]`.

frontend/README.md: added an "API Types" section documenting that the file
is generated, must not be edited by hand, and how to regenerate it (start
backend, npm run gen:types; or run the CLI with a custom URL).

To produce the initial committed file without standing up Docker/Postgres,
the schema was dumped offline from the app (app.openapi() with a dummy
DATABASE_URL — create_async_engine does not connect at import) into a temp
file, generated from it, and the temp file deleted. The committed script
remains the canonical regen path against the live server.

No backend code changed; backend suite unaffected (216 green).

### 2026-05-31 (Citation paths: relative at source, cross-platform)
Fixed citation file paths to be repo-relative and correct on both Windows
and Linux. Root cause: chunks stored file_path as the absolute clone path,
and app/api/chat.py patched it at read time with a POSIX-only regex
(_TMP_SEGMENT_RE = /tmp[a-z0-9_]+/) that never matched Windows temp clone
paths (C:\Users\...\AppData\Local\Temp\tmpXXX\...) — and the Celery worker
runs natively on Windows in local dev.

Fixed at the source. app/workers/tasks.py: new _to_repo_relative(abs_path,
clone_root) helper — normalizes separators to '/' then uses
posixpath.relpath, the cross-platform-deterministic form of os.path.relpath
(does not depend on host path semantics, so the same forward-slash relative
path results on Windows and on Railway/Linux). run_indexing_pipeline now
relativizes each file against local_path (the clone root) before passing it
to parser.parse, so CodeChunk.file_path — and therefore ChromaDB metadata,
RAG citations, and the context shown to the LLM — is clean by construction.
The Stage 7 graph build now uses the same helper (replacing its inline
os.path.relpath), so chunk paths and graph node paths are derived
identically. The now-unused `import os` was removed.

app/api/chat.py: deleted _make_relative_path, _TMP_SEGMENT_RE, and the `re`
import; citations pass c.file_path straight through (already relative).

Trade-off accepted: repos indexed before this change keep absolute paths
until re-indexed. Acceptable — this is local-dev-only data, there is no prod
deployment yet (Phase 6 not started), and force_reindex=true drops and
rebuilds chunks + Chroma. Chose the source fix over a platform-robust
_make_relative_path because it makes paths clean by construction, improves
the LLM context (not just the API response), and lets the regex hack be
deleted entirely.

tests/workers/test_tasks.py: TestRepoRelativePath (6 tests) covers POSIX and
Windows-backslash clone roots, nested top-level dirs (no repo-name
prepending), trailing separator on the root, and asserts results carry no
backslashes or drive letters — all deterministic regardless of test host.
TestRelativeChunkPaths runs the full pipeline and asserts stored
CodeChunk.file_path values are repo-relative forward-slash (app/main.py,
app/utils.py). tests/api/test_chat.py: removed the TestMakeRelativePath
class and its import; the citation fixture is now already-relative and the
endpoint test verifies pass-through.

Full suite: 216 tests green.

### 2026-05-31 (CORS configuration)
Configurable CORS support added to the FastAPI backend. Frontend deploys
on Vercel and backend on Railway, so production requests are cross-origin.

app/main.py: CORSMiddleware allow_origins now driven by the
CORS_ALLOW_ORIGINS env var (comma-separated, whitespace-trimmed, empties
dropped), defaulting to http://localhost:3000 for local dev. Added
load_dotenv() at module top to match database.py/celery_app.py. Keeps
allow_credentials=True, allow_methods=["*"], allow_headers=["*"]. The
middleware wraps the whole ASGI app, so it also covers the GET
/repos/{id}/status SSE stream (the Access-Control-Allow-Origin header is
applied to streamed responses and to CORS preflight on that route).

tests/test_cors.py: 2 tests. First asserts a GET /health from origin
http://localhost:3000 returns access-control-allow-origin equal to the
origin and access-control-allow-credentials true. Second issues a CORS
preflight (OPTIONS + Access-Control-Request-Method: GET) against
/repos/{uuid}/status and asserts the same headers — confirming CORS
covers the SSE endpoint without starting the stream or hitting the DB.

Full suite: 213 tests green.

### 2026-05-31 (Phase 4 Step 5 + Phase 4 complete)
Phase 4 Step 5 complete. GET /repos/{repo_id}/graph endpoint built and
verified. Phase 4 (Dependency graph) is now fully done.

app/api/graph.py: new router APIRouter(prefix="/repos", tags=["graph"])
sharing the /repos prefix with repos.py. GET /{repo_id}/graph with
repo_id: UUID path param (FastAPI auto-validates) and resolved_only:
bool = False query param. 404 if repo missing, 400 if status !=
"completed" (mirrors chat.py validation). Loads FileNode rows ordered
imported_by_count DESC then file_path ASC (most-central files first,
deterministic ties), FileDependency rows ordered source_file ASC; when
resolved_only=true the edge query adds target_file IS NOT NULL.
node_count/edge_count reflect the returned (post-filter) lists. Returns
GraphResponse with repo_id=str(repo.id).

app/api/schemas.py: added GraphNodeResponse (file_path, language,
import_count, imported_by_count), GraphEdgeResponse (source_file,
target_file: str | None, import_raw), GraphResponse (repo_id: str,
node_count, edge_count, nodes, edges). repo_id is str not int as the
spec text said — repo ids are UUIDs throughout this codebase.

app/main.py: registered graph_router alongside repos_router and
chat_router.

tests/api/test_graph_endpoint.py: 7 tests using the async_client +
db_session fixtures. 404 on unknown repo, 400 on not-completed repo,
200 with correct node/edge counts and payload shape (incl. an
unresolved target_file=None edge), edges sorted by source_file asc,
resolved_only=true drops the unresolved edge (edge_count 2 → 1, no null
targets), nodes sorted imported_by_count desc (core.py imported_by=3
first), empty graph (completed repo, no rows) → 200 with empty lists
and zero counts.

Full suite: 211 tests green.

Phase 4 summary (Steps 1–5):
- Step 1: FileNode (repo_id, file_path, language, import_count,
  imported_by_count; unique (repo_id, file_path)) and FileDependency
  (repo_id, source_file, target_file NULLABLE, import_raw; index on
  (repo_id, source_file)) ORM models + Alembic migration, CASCADE on
  repository delete.
- Step 2: per-file import extractors (app/graph/extractors/) emitting
  ImportEdge(source_file, import_raw, target_module). PythonExtractor
  (stdlib ast, one edge per imported name), JavaScriptExtractor (regex,
  one edge per statement, .js/.jsx/.ts/.tsx), registry.get_extractor
  cached by class. Never raise.
- Step 3: app/graph/builder.py — resolve_import (Python relative/
  absolute with .py and __init__.py and symbol-strip fallbacks; JS
  relative with extension and /index fallbacks; bare specifiers and
  third-party → None; never raises) and GraphBuilder.build(repo_id) →
  GraphBuildResult, persisting FileNode + FileDependency via a sync
  session, computing in/out degree from resolved edges, idempotent
  rebuild, per-file errors swallowed.
- Step 4: GraphBuilder wired into run_indexing_pipeline as a non-fatal
  phase after ChromaDB storage. Progress 10/30/80/85/95/100; graph
  failure logged + rolled back, job still completes.
- Step 5: GET /repos/{repo_id}/graph read endpoint (this entry).

Next: Phase 5 — Frontend.

### 2026-05-31 (Phase 4 Step 4)
Phase 4 Step 4 complete. GraphBuilder wired into the index_repository
Celery task.

app/workers/tasks.py: GraphBuilder integrated as a new phase after
ChromaDB storage, before job completion. Progress checkpoints updated
across all phases: 10% repo cloned, 30% files walked, 80% parsing and
embedding done, 85% starting graph build with status message "Building
dependency graph...", 95% graph build done, 100% complete. GraphBuilder
instantiated with the sync DB session already in use by the task and
the already-collected all_file_paths list — repo is not re-walked.
Graph build wrapped in try/except: on any exception the error is logged
as a warning and the task continues normally, job still completes with
status "completed". GraphBuilder failure is non-fatal by design.

tests/workers/test_tasks.py: Tests updated and added covering graph
build is called after embedding, graph build failure does not fail the
job, job ends as "completed" even when GraphBuilder raises, progress
reaches 85 and 95 during the graph phase.

Full suite: 204 tests green.

### 2026-05-31 (Phase 4 Step 3)
Phase 4 Step 3 complete. Graph builder service built and verified.

app/graph/builder.py: resolve_import module-level helper and
GraphBuilder class.

resolve_import(source_file, target_module, repo_root, all_file_paths)
-> str | None. For Python: relative imports (leading dots) resolve
relative to source_file's directory — one dot is same package, two
dots is parent package. Absolute imports convert dot-separated module
path to file path and try .py suffix then __init__.py fallback.
Returns None for third-party/stdlib imports not found in repo. For
JS/TS: relative specifiers (leading . or ..) resolve from source
file's directory trying exact match then .js, .ts, .jsx, .tsx suffixes
then /index.js, /index.ts fallbacks. Non-relative specifiers (react,
lodash etc.) return None immediately. Never raises under any input.

GraphBuildResult dataclass with node_count, edge_count,
unresolved_count fields.

GraphBuilder.__init__(db_session, repo_root, all_file_paths): takes
sync SQLAlchemy session matching existing Celery task DB session
pattern.

GraphBuilder.build(repo_id) -> GraphBuildResult:
1. Deletes existing FileNode and FileDependency rows for repo_id.
2. For each file in all_file_paths: gets extractor via registry,
   skips unsupported extensions, reads file from disk, calls
   extractor.extract(), skips file silently on read error.
3. For each ImportEdge calls resolve_import — creates FileDependency
   row whether resolved or not, target_file=None when unresolved.
4. Computes import_count and imported_by_count per file from resolved
   edges, bulk-inserts FileNode rows.
5. Bulk-inserts FileDependency rows.
6. Commits and returns GraphBuildResult.
Never raises — per-file errors caught and logged, build continues.

tests/graph/test_builder.py: 17 tests covering single Python file with
imports produces correct FileNode and FileDependency rows, relative
import resolves correctly, unresolvable third-party import produces
FileDependency with target_file=None, JS relative import resolves
correctly, JS node_modules import produces target_file=None, re-running
build() on same repo_id replaces old rows (idempotent), file with read
error is skipped and rest of graph is built, GraphBuildResult counts
are accurate. All resolve_import edge cases verified: Python absolute,
Python relative one and two dots, __init__ fallback, JS extension
fallback, JS index file fallback, third-party returns None, never
raises on bad input.

Full suite: 199 tests green.

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