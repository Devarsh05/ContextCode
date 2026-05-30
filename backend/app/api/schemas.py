from uuid import UUID

from pydantic import BaseModel, field_validator


class IndexRequest(BaseModel):
    repo_url: str
    force_reindex: bool = False


class IndexResponse(BaseModel):
    repo_id: UUID
    job_id: UUID
    status: str


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
