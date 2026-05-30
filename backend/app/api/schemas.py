from uuid import UUID

from pydantic import BaseModel


class IndexRequest(BaseModel):
    repo_url: str
    force_reindex: bool = False


class IndexResponse(BaseModel):
    repo_id: UUID
    job_id: UUID
    status: str
