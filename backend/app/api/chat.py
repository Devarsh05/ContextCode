import re
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas import ChatRequest, ChatResponse, CitationResponse
from app.models.database import get_db
from app.models.repository import Repository
from app.rag.pipeline import RAGPipeline

router = APIRouter(tags=["chat"])

_pipeline = RAGPipeline()

# Matches Python's tempfile.mkdtemp() directory names: tmp followed by
# lowercase letters, digits, and underscores.
_TMP_SEGMENT_RE = re.compile(r"/tmp[a-z0-9_]+/")


def _make_relative_path(absolute_path: str, repo_name: str) -> str:
    normalized = absolute_path.replace("\\", "/")
    match = _TMP_SEGMENT_RE.search(normalized)
    if match:
        relative = normalized[match.end():]
        if not relative.startswith(repo_name + "/"):
            relative = repo_name + "/" + relative
        return relative
    return normalized


@router.post("/chat", response_model=ChatResponse)
async def chat(
    body: ChatRequest,
    db: AsyncSession = Depends(get_db),
) -> ChatResponse:
    try:
        repo_uuid = UUID(body.repo_id)
    except (ValueError, AttributeError):
        raise HTTPException(status_code=404, detail="Repository not found")

    result = await db.execute(select(Repository).where(Repository.id == repo_uuid))
    repo = result.scalar_one_or_none()

    if repo is None:
        raise HTTPException(status_code=404, detail="Repository not found")

    if repo.status != "completed":
        raise HTTPException(
            status_code=400,
            detail="Repository is not fully indexed yet",
        )

    rag_result = await _pipeline.answer(body.repo_id, body.question)

    citations = [
        CitationResponse(
            file_path=_make_relative_path(c.file_path, repo.name),
            function_name=c.function_name,
            start_line=c.start_line,
            end_line=c.end_line,
            chunk_type=c.chunk_type,
            snippet=c.snippet,
        )
        for c in rag_result["citations"]
    ]

    return ChatResponse(answer=rag_result["answer"], citations=citations)
