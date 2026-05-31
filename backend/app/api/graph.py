from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas import GraphEdgeResponse, GraphNodeResponse, GraphResponse
from app.models.database import get_db
from app.models.graph import FileDependency, FileNode
from app.models.repository import Repository

router = APIRouter(prefix="/repos", tags=["graph"])


@router.get("/{repo_id}/graph", response_model=GraphResponse)
async def get_graph(
    repo_id: UUID,
    resolved_only: bool = False,
    db: AsyncSession = Depends(get_db),
) -> GraphResponse:
    repo_result = await db.execute(
        select(Repository).where(Repository.id == repo_id)
    )
    repo = repo_result.scalar_one_or_none()

    if repo is None:
        raise HTTPException(status_code=404, detail="Repository not found")

    if repo.status != "completed":
        raise HTTPException(
            status_code=400,
            detail="Repository is not fully indexed yet",
        )

    # Nodes ordered most-imported first (most "central" files at the top);
    # file_path is a secondary key so ties are deterministic.
    node_result = await db.execute(
        select(FileNode)
        .where(FileNode.repo_id == repo_id)
        .order_by(FileNode.imported_by_count.desc(), FileNode.file_path.asc())
    )
    nodes = node_result.scalars().all()

    edge_query = select(FileDependency).where(FileDependency.repo_id == repo_id)
    if resolved_only:
        edge_query = edge_query.where(FileDependency.target_file.isnot(None))
    edge_query = edge_query.order_by(FileDependency.source_file.asc())
    edge_result = await db.execute(edge_query)
    edges = edge_result.scalars().all()

    node_responses = [
        GraphNodeResponse(
            file_path=n.file_path,
            language=n.language,
            import_count=n.import_count,
            imported_by_count=n.imported_by_count,
        )
        for n in nodes
    ]
    edge_responses = [
        GraphEdgeResponse(
            source_file=e.source_file,
            target_file=e.target_file,
            import_raw=e.import_raw,
        )
        for e in edges
    ]

    return GraphResponse(
        repo_id=str(repo.id),
        node_count=len(node_responses),
        edge_count=len(edge_responses),
        nodes=node_responses,
        edges=edge_responses,
    )
