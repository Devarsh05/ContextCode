from uuid import UUID

from pydantic import BaseModel, field_validator


class ErrorResponse(BaseModel):
    """Standard error body (matches FastAPI's HTTPException shape).

    Used to document the 401 / 429 responses of the cost-control gate.
    """

    detail: str


class IndexRequest(BaseModel):
    repo_url: str
    force_reindex: bool = False


class IndexResponse(BaseModel):
    repo_id: UUID
    job_id: UUID
    status: str


class RepoResponse(BaseModel):
    repo_id: UUID
    url: str
    name: str
    status: str
    file_count: int | None = None


class CitationResponse(BaseModel):
    file_path: str
    function_name: str
    start_line: int
    end_line: int
    chunk_type: str
    snippet: str


class ChatRequest(BaseModel):
    repo_id: str
    question: str

    @field_validator("question")
    @classmethod
    def question_must_not_be_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("question must not be empty")
        return v.strip()


class ChatResponse(BaseModel):
    answer: str
    citations: list[CitationResponse]


class GraphNodeResponse(BaseModel):
    file_path: str
    language: str
    import_count: int
    imported_by_count: int


class GraphEdgeResponse(BaseModel):
    source_file: str
    target_file: str | None
    import_raw: str


class GraphResponse(BaseModel):
    repo_id: str
    node_count: int
    edge_count: int
    nodes: list[GraphNodeResponse]
    edges: list[GraphEdgeResponse]
