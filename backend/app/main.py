import os

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.chat import router as chat_router
from app.api.graph import router as graph_router
from app.api.repos import router as repos_router

load_dotenv()

# Comma-separated list of allowed origins. Frontend (Vercel) and backend
# (Railway) live on different domains, so requests are cross-origin in prod.
# Defaults to the local Next.js dev server.
_CORS_ALLOW_ORIGINS = [
    origin.strip()
    for origin in os.environ.get("CORS_ALLOW_ORIGINS", "http://localhost:3000").split(",")
    if origin.strip()
]

app = FastAPI(title="ContextCode API")

# Applies to every route, including the GET /repos/{id}/status SSE stream —
# CORSMiddleware wraps the whole ASGI app, so streamed responses get the
# Access-Control-Allow-Origin header too.
app.add_middleware(
    CORSMiddleware,
    allow_origins=_CORS_ALLOW_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(repos_router)
app.include_router(chat_router)
app.include_router(graph_router)


@app.get("/health")
async def health():
    return {"status": "ok"}
