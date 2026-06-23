# ContextCode

**Understand any codebase in minutes.** Paste a public GitHub URL, and ContextCode indexes it with AST-aware parsing, lets you chat with the codebase via RAG with real citations, and visualizes the dependency graph with danger-zone analysis.

[**Live Demo**](https://context-code.vercel.app) — no signup, no API key, three pre-indexed repos ready to chat with right now.

![ContextCode landing page](docs\images\landing page.png)


---

## What it does

1. **Index** — paste a GitHub URL (or pick one of the pre-loaded demo repos). ContextCode clones it, parses every Python/JS/TS file with Tree-sitter at function- and class-level granularity, and embeds each chunk.
2. **Chat** — ask questions in plain English. Answers are grounded in retrieved chunks and cite the exact file and line range they came from — no hallucinated file paths.
3. **Visualize** — an interactive dependency graph (React Flow) shows which files import which, with centrality ranking to surface the highest-risk "hub" files in the codebase.

![Chat with citations](docs/images/placeholder-chat.png)
![Dependency graph](docs/images/placeholder-graph.png)

---

## Why this is interesting

- **Provider-swappable AI layer.** Both the embedding model and the LLM sit behind clean interfaces (`Embedder`, `LLMClient`). Local dev runs on `sentence-transformers` (MiniLM, free, fast iteration); production runs on OpenAI (`text-embedding-3-small`) for quality. Swapping providers is a config change, not a refactor — no application code calls a provider directly.
- **AST-aware chunking, not line-splitting.** Tree-sitter parses real function and class boundaries per language, so a chunk is never a code snippet cut mid-function. Module-level chunks capture imports and top-level statements without overlapping function/class ranges.
- **A real production cost-control architecture.** Public chat is genuinely free to try — no signup, no API key — but it's protected by Cloudflare Turnstile-minted session tokens, dual rate limits (per-session and global daily), and a hard scope restriction to pre-indexed demo repos. Arbitrary-URL indexing (the expensive operation) stays behind a separate gate. This keeps the live demo open to recruiters while keeping OpenAI spend bounded and bot-proof.
- **Centrality-ranked dependency graph.** Rather than just drawing import edges, the graph builder ranks files by centrality to highlight which modules are structurally load-bearing — the files most likely to break things if touched carelessly.

---

## Architecture

```
┌─────────────┐         ┌──────────────────────────────────────────┐
│   Vercel    │  HTTPS  │                  Railway                  │
│             ├────────►│  ┌────────┐  ┌────────────┐  ┌──────────┐ │
│  Next.js 14 │         │  │FastAPI │──│Celery worker│──│ ChromaDB │ │
│  React Flow │◄────────┤  │  API   │  │(AST parsing,│  │ (vector  │ │
│  TanStack Q.│   SSE   │  └───┬────┘  │ embeddings) │  │  store)  │ │
└─────────────┘         │      │       └─────────────┘  └──────────┘ │
                         │      │                                     │
                         │  ┌───┴────┐         ┌───────┐              │
                         │  │Postgres│         │ Redis │              │
                         │  └────────┘         └───────┘              │
                         └──────────────────────────────────────────┘
```

Indexing runs as a background Celery job; the API's SSE endpoint only reads job progress from Postgres — it never does the parsing/embedding work itself, keeping the event loop responsive throughout a long-running index.

---

## Tech stack

| Layer | Technology |
|---|---|
| Backend | FastAPI, Python 3.11, Celery, Redis, ChromaDB, PostgreSQL |
| Parsing | Tree-sitter (Python, JavaScript, TypeScript) |
| Embeddings | OpenAI `text-embedding-3-small` (prod) / `all-MiniLM-L6-v2` (dev), behind a swappable interface |
| LLM | OpenAI, behind a swappable interface |
| Frontend | Next.js 14 (App Router), TypeScript, Tailwind, React Flow, TanStack Query |
| Bot protection | Cloudflare Turnstile |
| Deploy | Railway (API, worker, ChromaDB, Postgres, Redis) + Vercel (frontend) |
| Testing | pytest, Playwright (E2E) |

---

## Engineering challenges worth a closer look

**Shared vector store across isolated containers.** Railway runs the API and Celery worker as separate containers with no shared filesystem. Moving ChromaDB from an embedded `PersistentClient` to a standalone service meant both the API and worker had to explicitly target the same `HttpClient` host — if that wiring is even slightly wrong (a missing host var, a mismatched token env-var name), both services silently fall back to isolated local instances that never see each other's data. No error, no crash — just chat answers with zero retrieved context. Diagnosing and fixing this class of "looks fine, silently wrong" bug is documented in detail in [`docs/SESSION_LOG.md`](docs/SESSION_LOG.md).

**A public demo that can't be abused.** Letting anyone chat with no signup is good UX and bad economics unless it's actually rate-limited correctly. The session-based gate (Turnstile mint → per-session quota → global daily quota, with atomic Redis INCR/DECR-on-rejection) took a few iterations to get right — an early version had a TTL race condition that could let the daily quota silently roll over mid-window.

Full debugging history, including deploy-pipeline gotchas (stale builds, env-var bake timing) and the demo-mode rollout, is in [`docs/SESSION_LOG.md`](docs/SESSION_LOG.md).

---

## Running locally

```bash
# 1. Start Postgres + Redis
docker compose up -d

# 2. Backend (from /backend, with a virtualenv active)
pip install -r requirements.txt
alembic upgrade head
celery -A app.workers.celery_app worker --loglevel=info   # --pool=solo on Windows
uvicorn app.main:app --reload

# 3. Frontend (from /frontend)
npm install
npm run dev
```

See [`CLAUDE.md`](CLAUDE.md) for full local-dev conventions, environment variable reference, and architecture rules.

---

## What this is not

This is a portfolio project, not a production SaaS. By design, it doesn't include: multi-user auth, autonomous coding agents, code generation/copilot features, or GitHub PR automation. The scope is deliberately narrow — codebase understanding via RAG + dependency visualization, done well — rather than broad.

---

## License

MIT
