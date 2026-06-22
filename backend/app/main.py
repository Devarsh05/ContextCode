from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.chat import router as chat_router
from app.api.demo_session import router as demo_router
from app.api.graph import router as graph_router
from app.api.repos import router as repos_router
from app.config import get_settings
from app.rate_limit import RateLimitExceeded, limiter, rate_limit_handler



# Comma-separated allowed origins (CORS_ALLOW_ORIGINS). Frontend (Vercel) and
# backend (Railway) live on different domains, so requests are cross-origin in
# prod. Defaults to the local Next.js dev server. Credentials are OFF — there is
# no auth, and "*"-style credentialed CORS is a footgun.
app = FastAPI(title="ContextCode API")

# Per-IP rate limiting on the token-spending endpoints (see app/rate_limit.py).
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, rate_limit_handler)

# Applies to every route, including the GET /repos/{id}/status SSE stream —
# CORSMiddleware wraps the whole ASGI app, so streamed responses get the
# Access-Control-Allow-Origin header too.
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(repos_router)
app.include_router(chat_router)
app.include_router(graph_router)
app.include_router(demo_router)


@app.get("/health")
async def health():
    return {"status": "ok"}
