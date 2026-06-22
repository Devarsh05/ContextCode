"""Idempotent demo-repo seeding.

Marks a curated set of already-indexed repositories as demos (``is_demo=True``)
so the demo-first access flow can surface them on the ungated ``GET
/repos/demos`` endpoint.

This routine only flags rows that ALREADY exist locally. A demo repo that has
not been indexed yet is logged and skipped — it is never fabricated, and the
normal index pipeline is never invoked from here. Actually indexing the demo
repos is a separate ops step (run against prod) in a later phase.

Run as an ops step:  ``python -m app.services.demo_seed``
"""
from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.repository import Repository

logger = logging.getLogger(__name__)

# Canonical GitHub URLs of the curated demo repos. Matched verbatim against
# Repository.url, which stores the URL exactly as supplied to POST /repos/index.
DEMO_REPO_URLS = [
    "https://github.com/encode/databases",
    "https://github.com/psf/requests",
    "https://github.com/colinhacks/zod",
]


async def seed_demo_repos(session: AsyncSession) -> dict[str, int]:
    """Flag existing repos as demos. Idempotent: re-running is a no-op.

    Returns counts of ``flagged`` (newly marked), ``already`` (already a demo),
    and ``missing`` (not present locally, skipped).
    """
    flagged = 0
    already = 0
    missing = 0

    for url in DEMO_REPO_URLS:
        result = await session.execute(
            select(Repository).where(Repository.url == url)
        )
        repo = result.scalar_one_or_none()

        if repo is None:
            logger.warning(
                "Demo repo not present locally, skipping: %s "
                "(index it via the normal pipeline first)",
                url,
            )
            missing += 1
            continue

        if repo.is_demo:
            already += 1
            continue

        repo.is_demo = True
        flagged += 1

    await session.commit()

    logger.info(
        "Demo seed complete: flagged=%d already=%d missing=%d",
        flagged,
        already,
        missing,
    )
    return {"flagged": flagged, "already": already, "missing": missing}


async def _main() -> None:
    from app.models.database import AsyncSessionLocal

    async with AsyncSessionLocal() as session:
        await seed_demo_repos(session)


if __name__ == "__main__":
    import asyncio

    logging.basicConfig(level=logging.INFO)
    asyncio.run(_main())
