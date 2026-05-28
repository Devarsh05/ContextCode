import asyncio
import logging
import time
import uuid

from sqlalchemy import update

from app.workers.celery_app import app

logger = logging.getLogger(__name__)


async def _update_job(job_id: str, **fields) -> None:
    """
    Update IndexingJob fields by primary key.

    Called via asyncio.run() from the sync Celery task (safe: no running
    event loop in a worker process). Called directly as an awaitable in
    async tests.
    """
    from app.models.database import AsyncSessionLocal
    from app.models.indexing_job import IndexingJob

    async with AsyncSessionLocal() as session:
        await session.execute(
            update(IndexingJob)
            .where(IndexingJob.id == uuid.UUID(job_id))
            .values(**fields)
        )
        await session.commit()


@app.task(bind=True, name="app.workers.tasks.index_repository")
def index_repository(self, repo_url: str, job_id: str) -> dict:
    """
    Placeholder indexing task — sleeps 2 s and writes two status updates.
    Will be fully implemented in Phase 4 (clone → parse → embed).
    """
    logger.info("indexing %s for job %s", repo_url, job_id)

    asyncio.run(
        _update_job(job_id, status="running", progress_pct=0, current_stage="cloning")
    )

    time.sleep(2)

    asyncio.run(
        _update_job(
            job_id, status="completed", progress_pct=100, current_stage=None
        )
    )

    return {"job_id": job_id, "status": "completed"}
