from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.cost_gate import require_chat_access
from app.api.schemas import (
    ChatRequest,
    ChatResponse,
    CitationResponse,
    ErrorResponse,
)
from app.config import get_settings
from app.models.database import get_db
from app.models.repository import Repository
from app.rag.pipeline import RAGPipeline
from app.rate_limit import limiter

router = APIRouter(tags=["chat"])

_pipeline = RAGPipeline()


@router.post(
    "/chat",
    response_model=ChatResponse,
    responses={
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        429: {"model": ErrorResponse},
    },
)
@limiter.limit(get_settings().rate_limit_chat)
async def chat(
    request: Request,
    body: ChatRequest,
    db: AsyncSession = Depends(get_db),
    _gate: None = Depends(require_chat_access),
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

    # file_path is already repo-relative (stored that way at index time).
    citations = [
        CitationResponse(
            file_path=c.file_path,
            function_name=c.function_name,
            start_line=c.start_line,
            end_line=c.end_line,
            chunk_type=c.chunk_type,
            snippet=c.snippet,
        )
        for c in rag_result["citations"]
    ]

    return ChatResponse(answer=rag_result["answer"], citations=citations)
