# ContextCode — Session Log

New entries go here (newest first). Update `## Current Status` in CLAUDE.md when a phase/step completes.

### 2026-06-18 (Phase 6 Step 0 — Deploy-prep code changes)
Pre-flight changes to make the backend deployable on Railway + Vercel. No infra
work: nothing deployed, no Railway/Vercel touched, no remote alembic. Branch
`phase-6/deploy-prep`.

New `app/config.py` — a single pydantic-settings `Settings` schema centralizing
every deploy env var (DATABASE_URL, REDIS_URL, CHROMA_HOST/PORT/TOKEN,
CHROMA_PERSIST_PATH, EMBEDDING_PROVIDER, OPENAI_API_KEY, CORS_ALLOW_ORIGINS, the
rate-limit values). Every field has a default so importing it never explodes in a
partial env. No `env_file` — it reads `os.environ`, composing with the existing
`load_dotenv()` calls. `get_settings()` returns a **fresh instance per call**
(deliberately not cached) so the env-patch test style in the suite is honored. A
`model_validator` defaults `rate_limit_storage_uri` to `redis_url`; a `cors_origins`
property comma-splits/trims the origins.

Chroma (`app/services/vector_store.py`) — added `create_chroma_client(persist_path)`:
returns `chromadb.HttpClient(host, port, headers=Bearer CHROMA_TOKEN)` when
CHROMA_HOST is set (so the API and Celery worker share one Chroma), else the
embedded `PersistentClient` as before. `VectorStore._get_client()` now routes
through it; the `persist_path` constructor arg and `./chroma_data` default are kept
so the existing store tests (no CHROMA_HOST → PersistentClient) pass untouched.
`docker-compose.yml` gained a pinned `chromadb/chroma:1.5.9` service (matches the
1.5.9 client) with a named `chroma_data:/data` volume, port 8000, and a
`/api/v2/heartbeat` healthcheck. `.env.example` sets `CHROMA_HOST=localhost` so
local dev uses HttpClient too, matching prod.

Embeddings (`app/services/embeddings.py`) — `LocalEmbedder.dimension` now comes from
the loaded model (`get_sentence_embedding_dimension()`), removing the hardcoded
`_DIMENSION = 384`; dimension is sourced from the active provider. The
sentence-transformers import was already lazy (inside `_get_model()`); kept that way
so the torch-free prod image imports cleanly. `get_embedder()` reads
`get_settings().embedding_provider`. Requirements split: base `requirements.txt`
drops `sentence-transformers` (and thus torch) and adds `slowapi` +
`pydantic-settings`; new `requirements-local.txt` is `-r requirements.txt` plus
`sentence-transformers` for local MiniLM.

CORS (`app/main.py`) — `allow_origins` now from `get_settings().cors_origins` and
**`allow_credentials=False`** (no auth → credentialed wildcard CORS removed). The
`allow_methods/allow_headers=["*"]` stay (safe without credentials).

Rate limiting — new `app/rate_limit.py`: slowapi `Limiter` keyed by client IP,
`storage_uri` defaulting to the Redis broker URL, `swallow_errors=True` so a Redis
blip fails OPEN (serves the request) rather than 500-ing — the right call for an
auth-less portfolio deploy. `main.py` wires `app.state.limiter` + the
`RateLimitExceeded` handler. POST `/repos/index` (`rate_limit_index`, 10/hour) and
POST `/chat` (`rate_limit_chat`, 30/minute) carry `@limiter.limit(...)` + a
`request: Request` param.

Dockerfile — installs `git` (shallow clone), base `requirements.txt` only (no
torch), and `CMD ["sh","-c","alembic upgrade head && uvicorn app.main:app --host
0.0.0.0 --port ${PORT:-8000}"]` (migrate then boot on Railway's $PORT). No
`--pool=solo` baked anywhere — the worker on Railway/Linux uses default prefork;
solo stays only in CLAUDE.md's local-dev docs.

Tests: `tests/services/test_chroma_factory.py` (HttpClient vs PersistentClient
selection + bearer header, mocked — no live server); `test_embeddings.py` extended
with provider-dimension assertions (local 384 from model, openai 1536) and a
subprocess-isolated lazy-import guard that blocks `torch`/`sentence_transformers`,
sets EMBEDDING_PROVIDER=openai, imports `app.main`, and asserts `get_embedder()`
returns `OpenAIEmbedder`; `test_cors.py` rewritten — credentials now asserted OFF,
plus origin parsing from CORS_ALLOW_ORIGINS; new `test_rate_limit.py` builds a
throwaway app via the real `build_limiter("memory://")` + handler and asserts a 429
past a 2/minute limit. `conftest.py` forces `RATE_LIMIT_STORAGE_URI=memory://`
(Redis-free, before any app import) and an autouse fixture `limiter.reset()`s
between tests so per-route limits don't accumulate across the session.

Verification: `pip install -r requirements-local.txt` OK; **pytest 232 passed**
(ruff/mypy not used by this project); `docker build -t contextcode-api .` succeeds
installing base reqs only — package list shows no torch/sentence-transformers,
clean (no CMD warning); `docker compose up -d` then
`Invoke-WebRequest http://localhost:8000/api/v2/heartbeat` → **200**
`{"nanosecond heartbeat":...}`. Static checks: `\b384\b` over `app/**` → no match;
`["*"]` matches only `allow_methods`/`allow_headers` (not `allow_origins`).

Next: Phase 6 deploy proper — Railway services (API + worker + Postgres + Redis +
Chroma) and Vercel frontend, with `EMBEDDING_PROVIDER=openai`,
`CORS_ALLOW_ORIGINS` = the Vercel domain, and the rate-limit envs set.

### 2026-06-17 (Phase 5 QA — Mobile graph zero-height collapse)
Final QA fix for the dependency-graph tab at 375px. Reported symptom: graph
canvas a black empty box with no nodes, controls/legend rendering fine above and
below.

Root cause (found by Playwright DOM instrumentation, not by reading CSS — the
first read led to a wrong conclusion that is worth recording). The ReactFlow
wrapper div in `components/repo/graph/graph-panel.tsx` carried
`h-[60vh] min-h-[420px] flex-1 ... lg:h-[640px]`. The wrapper itself measured
418px tall on mobile, but its child `.react-flow` measured `height: 0px`. React
Flow's base CSS is `.react-flow { height: 100% }`, which only resolves against a
parent with a *definite* height. The canvas row is `flex-col` below `lg`, so the
wrapper is a vertical flex item; its `flex-1` (`flex: 1 1 0%`) makes flex-basis
govern the *main (vertical)* axis, overriding `h-[60vh]` and leaving the wrapper's
height flex-derived/indefinite for percentage resolution. So `height: 100%` fell
back to auto → content height → 0 (React Flow's inner panes are absolutely
positioned). On desktop the row is `lg:flex-row`, so flex-basis governs *width*
and height comes from the explicit `lg:h-[640px]` (definite) — which is exactly
why desktop always worked and mobile collapsed. `toBeVisible()` did not catch it:
the node stayed in the DOM with a bounding box, just clipped outside the 0px pane.

Fix: scoped flex to the breakpoint where the row layout actually exists —
`flex-1` → `lg:flex-1`. Below `lg` the wrapper is a normal block item and
`h-[60vh]` is a definite height, so `.react-flow` resolves to ~418px and the graph
renders. (The task's literal `md:flex-1` was rejected: the layout stays `flex-col`
through the md→lg range, so `md:flex-1` would reintroduce the collapse on tablets;
`lg:flex-1` matches the `lg:flex-row` switch.)

Also added fitView-on-resize: extracted the canvas into an inner `GraphCanvas`
wrapped in `<ReactFlowProvider>` so it can use `useReactFlow()`; a `ResizeObserver`
on the container ref calls `fitView()` on every dimension change, re-framing the
graph when crossing the mobile↔desktop breakpoint (canvas height goes 60vh ↔
640px and the 320px detail panel joins/leaves the row). No changes to node colors,
danger-zone tiers, controls, legend, or selection logic.

Regression test: `e2e/graph-mobile.spec.ts` (mocked backend, 375px). Asserts the
`.react-flow` pane height > 200px and the node's center sits inside the pane rect
(not just `toBeVisible`, which the original bug passed), then resizes
375 → 1280 → 375 and re-asserts the node stays framed.

Verification: `npx tsc --noEmit` clean; Playwright 2/2 (happy-path + graph-mobile)
green; vitest 42/42 green. Visually confirmed via screenshots at 375px: both
nodes (`main.py` critical/red, `utils.py`) framed with the edge, controls, and
legend, before and after the resize round-trip.

### 2026-06-03 (Phase 5 Step 7 — Polish + E2E) — Phase 5 COMPLETE
Polish pass over the four surfaces (landing, progress, chat, graph). No data-layer
or feature changes; only existing Indigo Slate tokens, no new hex.

Progress: replaced the bare initial-load spinner in `repo-view.tsx` with
`indexing-progress-skeleton.tsx` — a Card mirroring `IndexingProgress`'s shape
(title/description lines, progress bar, one row per `STAGES` entry) so the swap to
the live stepper causes no layout shift. `IndexingError` gained an optional `title`
prop; `repo-view` now passes "Repository not found" (vs "Indexing failed") when
`repo.isError`, and that message wins over a transient SSE "connection lost" error.
EventSource cleanup on unmount/terminal/error was already correct — verified.

Chat: inline error turns now carry the originating `question` (added to
`AssistantMessage`) and render a ghost "Retry" button (chat-message.tsx). chat-panel
factored send into `ask(question, { withUserBubble })`; retry drops the failed turn
by id and re-asks without a duplicate user bubble. Focus rings added to empty-state
suggestion buttons. Thinking state + empty-citation handling untouched.

Graph: canvas row is now `flex-col lg:flex-row` with an explicit responsive height
(`h-[60vh] min-h-[420px] lg:h-[640px]`) on both the canvas and the loading skeleton,
and the detail panel is `w-full lg:w-80` — React Flow keeps a defined height and
stays pannable/zoomable on mobile instead of collapsing under the side panel.

Landing: already handled an unreachable backend via the mutation `onError` toast —
verified, no change.

Testing: added `@playwright/test` + `playwright.config.ts` (Chromium, webServer
`npm run dev`) and `e2e/happy-path.spec.ts`. All backend calls intercepted via
`page.route` — including a scripted `text/event-stream` body for the SSE status
endpoint (in-progress then `completed` frame). The graph route uses a RegExp so it
matches the `?resolved_only=` query string. Flow: enter URL → progress streams to
completion → workspace → send chat message → answer + citation visible → Graph tab →
node visible. `test:e2e` script added; vitest `exclude` gained `e2e`; test-results /
playwright-report gitignored.

Verification: tsc --noEmit clean, next lint clean, next build green (`/repo/[id]`
221 kB First Load JS, dominated by React Flow/dagre — no balloon), Playwright E2E
passes, 42 vitest tests green, hex grep over app/ + components/ empty.

Phase 5 summary: a complete dark-mode-first Next.js 14 frontend over the FastAPI
backend — design foundation + app shell (Step 1), typed API client + query hooks +
SSE (Step 2), landing hero/form (Step 3), indexing progress stepper (Step 4), RAG
chat with expandable citations (Step 5), React Flow dependency graph with danger
zones (Step 6), and this polish/states/responsive/a11y pass with a deterministic
mocked E2E (Step 7). Next: Phase 6 — Deploy (Vercel frontend, Railway backend).

### 2026-06-02 (Phase 5 Step 6 — Dependency graph)
Dependency graph tab. Packages added: reactflow, dagre, @types/dagre.

`frontend/lib/graph/select.ts`: pure graph-shaping module. `CentralityTier` (0–4 type).
`centralityTier(count, maxCount)` maps fan-in to a 5-step danger scale relative to the
most-imported node in the visible set (ratio ≤0.25 → tier 1, ≤0.5 → 2, ≤0.75 → 3, >0.75 →
4; 0 fan-in or zero max → tier 0). `selectVisibleGraph(nodes, edges, n, hideIsolated)`:
sorts nodes by imported_by_count desc (file_path tie-break), slices the top-N, retains edges
whose both endpoints are in the visible set — this also silently drops null-target edges
(unresolved/third-party imports can never satisfy the membership test). `hideIsolated` then
removes nodes not touched by any kept edge; the filter composes with top-N so a node whose
only neighbour fell outside the slider reads as isolated. `nodeEdges(filePath, allEdges)`
partitions the full (not just visible) edge list for the detail panel.

`frontend/lib/graph/tiers.ts`: `TIERS` record keyed by CentralityTier — peripheral (muted
slate 150×48px) → low (dim indigo, 168×52) → moderate (brighter indigo, 188×58) → high
(amber warning token, 212×64) → critical (red destructive, 240×72, glow box-shadow ring).
Size and colour both encode centrality to avoid relying on colour alone.

`frontend/lib/graph/layout.ts`: `layoutGraph(visible)` runs dagre LR (A→B = A imports B,
dependencies flow rightward into high-fan-in nodes). Converts dagre centre coordinates to
React Flow top-left positions. Edges styled muted-slate with ArrowClosed markers.

`frontend/components/repo/graph/dep-node.tsx`: custom React Flow node (type "dep") reading
`DepNodeData` (node + tier). `frontend/components/repo/graph/graph-controls.tsx`: top-N
slider (1–total) + "Hide isolated files" switch + visible-count label.
`frontend/components/repo/graph/graph-legend.tsx`: 5-tier colour/size legend.
`frontend/components/repo/graph/graph-panel.tsx`: loading skeletons, error Card with Retry,
empty-graph state, ReactFlow canvas with Background + Controls (fitView, DEFAULT_N=60,
proOptions.hideAttribution). GraphLegend pinned bottom-left behind backdrop-blur. Node click
toggles `selectedPath` (second click deselects); pane click clears. NodeDetailPanel rendered
in a 320 px side column when a node is selected. `frontend/components/repo/graph/
node-detail-panel.tsx`: file metadata (path, language, import/imported_by counts, tier),
incoming/outgoing edge lists drawn from the full edge set so neighbours outside top-N still
appear.

The original resolvedOnly switch was repurposed to "Hide isolated files" because
`resolved_only=true` had no visible effect — unresolved edges already carry `target_file=null`
and are implicitly dropped by `selectVisibleGraph` before any node is drawn. The API-level
filter changed the edge count but produced an identical canvas.

BUG: graph build was silently failing in Celery with a Postgres `NotNullViolation` on
`file_dependencies.target_file`. Root cause: the initial `a8e3f1c92d74` migration created the
column NOT NULL; the `d3b7e2f10a95` follow-up migration (Phase 4 Step 1) relaxed it, but a
dev DB that only applied the original migration retained the NOT NULL constraint. SQLite-based
tests build schema from `Base.metadata.create_all`, inherit ORM nullability, and can never
catch migration/DB drift. Fix: `backend/tests/migrations/test_target_file_nullable.py` added
as a regression guard — creates a throwaway Postgres DB, runs `alembic upgrade head`, and
inserts a `target_file=None` FileDependency row; a future migration that re-introduces NOT
NULL fails here, not in production. Test skips when DATABASE_URL is absent or non-Postgres.

`frontend/lib/graph/__tests__/select.test.ts`: 18 tests across centralityTier thresholds
(including boundary conditions), selectVisibleGraph top-N ordering and tie-breaking, edge
endpoint filtering, null-target-file drop, hide-isolated composition with top-N, and
nodeEdges incoming/outgoing partitioning.

Verification: tsc --noEmit clean, 18 select tests pass, migration regression test passes
against Postgres, next build green. Re-indexing confirmed graph renders and danger zones
display correctly.

Next: Phase 6 — Deploy (Vercel frontend, Railway backend).

### 2026-06-02 (Phase 5 Step 5 — Chat)
Chat tab built and tested. No backend changes.

`frontend/components/repo/chat/types.ts`: `ChatMessage` discriminated union — `user` role
(content: string) and `assistant` role (answer, citations array, optional isError flag).

`frontend/components/repo/chat/chat-panel.tsx`: messages in local component state only (no
persistence — multi-user/auth is out of scope). Empty state: centered MessagesSquare icon,
help text, 3 starter suggestion chips as pill buttons. Each submission appends a user message
then calls `chat.mutate({ repo_id, question })`; `onSuccess` appends the assistant turn;
`onError` appends an `isError` assistant bubble carrying the error string. While pending
`<ChatThinking>` is appended. `useEffect` on `[messages.length, chat.isPending]` calls
`bottomRef.current.scrollIntoView({ behavior: "smooth" })`.

`frontend/components/repo/chat/chat-message.tsx`: user bubbles right-aligned (primary bg);
assistant bubbles left-aligned (card bg, border). `isError` flips to destructive styling
with an AlertTriangle prefix. Citation block rendered only when `citations.length > 0` — a
zero-citation refusal answer shows no citation header, covering the clean empty-citation
case.

`frontend/components/repo/chat/chat-thinking.tsx`: three bouncing dots at 0/150/300 ms
`animationDelay`, `aria-live="polite"` for screen readers.

`frontend/components/repo/chat/chat-composer.tsx`: auto-growing Textarea (capped at 200 px
via `useEffect` on value resetting `el.style.height`). Enter submits; Shift+Enter inserts a
newline. Send button disabled when value is blank or pending. `aria-label="Ask a question
about this codebase"`.

`frontend/components/repo/chat/citation-card.tsx`: expandable citation. Collapsed header:
`formatCitationRange(citation)` (file_path:start-end; single-line collapses to file_path:line),
optional function_name in muted mono, chunk_type Badge. Clicking reveals a `<pre>` snippet
(max-h-72, font-mono, overflow-auto) via ChevronDown toggle with `aria-expanded`.

`frontend/lib/citations.ts`: `formatCitationRange()` pure helper.
`frontend/lib/citations.test.ts`: 3 tests (multi-line range, single-line collapse, path
preserved verbatim).

`frontend/components/repo/chat/__tests__/chat-panel.test.tsx`: 4 tests (Vitest + RTL +
mocked `postChat`): user message appears, answer + citation renders, empty-citation response
shows no citation block, thinking indicator appears while pending then clears on resolution,
error bubble on network failure.

Verification: tsc --noEmit clean, 4 chat-panel + 3 citations tests pass, next build green.

Next: Phase 5 Step 6 — dependency graph tab.

### 2026-06-02 (Phase 5 Step 4 — Indexing progress)
Indexing progress view. Added a backend GET /repos/{id} endpoint so the progress page can
read the repo URL (needed for Retry) and bootstrap status on cold load.

Backend: `GET /repos/{repo_id}` added to `app/api/repos.py` — validates UUID path param,
returns `RepoResponse` (repo_id, url, name, status, file_count), 404 on unknown.
`RepoResponse` added to `app/api/schemas.py`. 2 new tests in `backend/tests/test_repos_api.py`
(200 full shape, 404 detail). `frontend/types/api.d.ts` regenerated to expose `RepoResponse`.

Frontend: `frontend/lib/api/repos.ts` gains `getRepo(repoId)` calling the new endpoint.
`frontend/lib/api/types.ts` adds `RepoResponse` alias. `frontend/hooks/use-repo.ts`:
`useRepo(repoId)` TanStack Query hook, enabled when repoId is truthy.

`frontend/lib/indexing-stages.ts`: pure module mapping 7 backend `current_stage` keys
(cloning / walking / parsing / persisting / embedding / storing / building_graph) to
human-readable labels. `resolveStageIndex(status, currentStage, prevIndex)` is monotonic —
returns `prevIndex` when stage is unknown/null while still running, so the stepper never
snaps backwards between SSE frames. `frontend/lib/indexing-stages.test.ts`: 8 tests.

`frontend/components/repo/indexing-progress.tsx`: Card with an indeterminate animated bar
(`animate-indeterminate` keyframe added to tailwind.config.ts) while `progressPct` is null,
transitioning to shadcn `<Progress value={pct}>` once the backend provides a numeric value.
7-stage stepper: Check/emerald (done), spinning Loader2/primary (active), dimmed dot
(pending). `useRef(lastIndexRef)` holds last known stage index so renders never regress.

`frontend/components/repo/indexing-error.tsx`: destructive Card showing the error message;
"Retry indexing" button (disabled until canRetry + not retrying) and "Start over" link to /.

`frontend/components/repo/repo-view.tsx`: `RepoView` wraps `RepoViewInner` with a
`retryNonce` key — incrementing it remounts the inner tree and reopens the SSE connection.
`RepoViewInner` consumes `useRepo` + `useIndexingStatus`; live SSE `status` wins over
`repo.data?.status`. Retry calls `indexRepo({ url, forceReindex: true })`, invalidates
`["repo", repoId]`, and increments `retryNonce`. Initial-loading spinner for the brief
window before the first repo fetch and SSE frame arrive. Transitions to `<Workspace>` on
completed; to `<IndexingError>` on failed or repo-not-found.

Verification: tsc --noEmit clean, 8 indexing-stages tests pass, 2 new backend tests pass,
next build green.

Next: Phase 5 Step 5 — chat tab.

### 2026-06-02 (Phase 5 Step 3 — Landing page)
Landing page wired to the indexing backend. No backend changes.

`frontend/components/repo-url-form.tsx` (client component): `isGithubRepoUrl(value)` pure
validator — trims, prepends `https://` if no protocol (so `github.com/owner/repo` passes),
feeds `new URL()`, checks hostname is github.com or www.github.com, checks path has ≥ 2
non-empty segments. Only validation uses the normalised form; the raw trimmed string is what
`indexRepo({ url: value })` sends to the backend. `useIndexRepo` mutation: `onSuccess` →
`router.push(/repo/{repo_id})`; `onError` → sonner toast with the error message. `isPending`
disables input and button (Loader2 + "Analyzing" label replaces ArrowRight + "Analyze").

`frontend/app/page.tsx` remains a server component: eyebrow pill badge, `<h1>` with
`text-primary` emphasis span, subtitle paragraph, `<RepoUrlForm />` client island, caption
noting "Public repos · Python, JavaScript & TypeScript", three benefit cards (MessagesSquare /
Network / GitBranch, each with title + body) in a responsive 3-column grid. 21st.dev Magic
MCP produced no usable output; the hero was hand-built against the Step-1 Indigo Slate tokens.

Verification: no new tests (pure validator has no stateful logic); tsc --noEmit clean,
next lint clean, next build green.

Next: Phase 5 Step 4 — indexing progress experience.

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
