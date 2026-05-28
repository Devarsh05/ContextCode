import asyncio
import json
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sse_starlette.sse import EventSourceResponse

from app.api.schemas import IndexRequest, IndexResponse
from app.models.database import get_db
from app.models.indexing_job import IndexingJob
from app.models.repository import Repository
from app.services.ingestion import IngestionService
from app.workers.tasks import index_repository

router = APIRouter(prefix="/repos", tags=["repos"])


@router.post("/index", response_model=IndexResponse)
async def start_indexing(
    body: IndexRequest,
    db: AsyncSession = Depends(get_db),
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

    if repo is not None and repo.status == "completed":
        job_result = await db.execute(
            select(IndexingJob)
            .where(IndexingJob.repo_id == repo.id)
            .order_by(IndexingJob.created_at.desc())
            .limit(1)
        )
        job = job_result.scalar_one()
        return IndexResponse(repo_id=repo.id, job_id=job.id, status="completed")

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
