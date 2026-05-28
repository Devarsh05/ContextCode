from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.repos import router as repos_router

app = FastAPI(title="ContextCode API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(repos_router)


@app.get("/health")
async def health():
    return {"status": "ok"}
