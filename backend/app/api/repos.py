import asyncio
import json
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sse_starlette.sse import EventSourceResponse

from app.api.cost_gate import require_index_quota
from app.api.schemas import (
    DemoRepoResponse,
    ErrorResponse,
    IndexRequest,
    IndexResponse,
    RepoResponse,
)
from app.config import get_settings
from app.models.code_chunk import CodeChunk
from app.models.database import get_db
from app.models.indexing_job import IndexingJob
from app.models.repository import Repository
from app.rate_limit import limiter
from app.services.ingestion import IngestionService
from app.services.vector_store import get_vector_store
from app.workers.tasks import index_repository

router = APIRouter(prefix="/repos", tags=["repos"])


@router.post(
    "/index",
    response_model=IndexResponse,
    responses={401: {"model": ErrorResponse}, 429: {"model": ErrorResponse}},
)
@limiter.limit(get_settings().rate_limit_index)
async def start_indexing(
    request: Request,
    body: IndexRequest,
    db: AsyncSession = Depends(get_db),
    _quota: None = Depends(require_index_quota),
) -> IndexResponse:
    try:
        IngestionService.validate_github_url(body.repo_url)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    name = body.repo_url.rstrip("/").rsplit("/", 1)[-1]

    result = await db.execute(
        select(Repository).where(Repository.url == body.repo_url)
    )
    repo = result.scalar_one_or_none()

    if repo is not None:
        if body.force_reindex:
            await db.execute(delete(CodeChunk).where(CodeChunk.repo_id == repo.id))
            get_vector_store().drop_collection(str(repo.id))
            job = IndexingJob(repo_id=repo.id)
            db.add(job)
            await db.flush()
            await db.commit()
            index_repository.delay(body.repo_url, str(job.id), str(repo.id))
            return IndexResponse(repo_id=repo.id, job_id=job.id, status="queued")
        else:
            job_result = await db.execute(
                select(IndexingJob)
                .where(IndexingJob.repo_id == repo.id)
                .order_by(IndexingJob.created_at.desc())
                .limit(1)
            )
            job = job_result.scalar_one()
            return IndexResponse(repo_id=repo.id, job_id=job.id, status=job.status)

    if repo is None:
        repo = Repository(url=body.repo_url, name=name)
        db.add(repo)
        await db.flush()

    job = IndexingJob(repo_id=repo.id)
    db.add(job)
    await db.flush()
    await db.commit()

    index_repository.delay(body.repo_url, str(job.id), str(repo.id))

    return IndexResponse(repo_id=repo.id, job_id=job.id, status="queued")


@router.get("/demos", response_model=list[DemoRepoResponse])
async def list_demo_repos(
    db: AsyncSession = Depends(get_db),
) -> list[DemoRepoResponse]:
    """List the curated demo repositories (read-only, ungated).

    Declared before ``/{repo_id}`` so the literal path is matched first.
    """
    result = await db.execute(
        select(Repository)
        .where(Repository.is_demo.is_(True))
        .order_by(Repository.name)
    )
    repos = result.scalars().all()
    return [
        DemoRepoResponse(
            id=repo.id,
            name=repo.name,
            url=repo.url,
            file_count=repo.file_count,
            status=repo.status,
        )
        for repo in repos
    ]


@router.get("/{repo_id}", response_model=RepoResponse)
async def get_repo(
    repo_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> RepoResponse:
    result = await db.execute(select(Repository).where(Repository.id == repo_id))
    repo = result.scalar_one_or_none()
    if repo is None:
        raise HTTPException(status_code=404, detail="Repository not found")
    return RepoResponse(
        repo_id=repo.id,
        url=repo.url,
        name=repo.name,
        status=repo.status,
        file_count=repo.file_count,
    )


@router.get("/{repo_id}/status")
async def repo_status(
    repo_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> EventSourceResponse:
    repo_result = await db.execute(
        select(Repository).where(Repository.id == repo_id)
    )
    if repo_result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Repository not found")

    async def event_generator():
        while True:
            # expire_all forces SQLAlchemy to re-fetch from DB on next access,
            # bypassing the identity-map cache so each poll sees fresh data.
            await db.run_sync(lambda s: s.expire_all())
            job_result = await db.execute(
                select(IndexingJob)
                .where(IndexingJob.repo_id == repo_id)
                .order_by(IndexingJob.created_at.desc())
                .limit(1)
            )
            job = job_result.scalar_one_or_none()

            if job is None:
                yield {"data": json.dumps({"error": "No indexing job found"})}
                return

            yield {
                "data": json.dumps({
                    "status": job.status,
                    "progress_pct": job.progress_pct,
                    "current_stage": job.current_stage,
                    "error_message": job.error_message,
                })
            }

            if job.status in ("completed", "failed"):
                return

            await asyncio.sleep(1)

    return EventSourceResponse(event_generator())
