"""Tests for POST /chat endpoint."""

import uuid
from unittest.mock import AsyncMock, patch

import pytest

from app.models.repository import Repository
from app.rag.pipeline import Citation


_CITATION = Citation(
    file_path="/tmp/tmpABC/databases/backends/mysql.py",
    function_name="connect",
    start_line=10,
    end_line=20,
    chunk_type="function",
    snippet="def connect(): ...",
)

_MOCK_ANSWER = {
    "answer": "The connect function [1] handles connections.",
    "citations": [_CITATION],
}


async def test_chat_returns_200_with_answer_and_citations(async_client, db_session):
    repo = Repository(
        url="https://github.com/encode/databases",
        name="databases",
        status="completed",
    )
    db_session.add(repo)
    await db_session.commit()

    with patch("app.rag.pipeline.RAGPipeline.answer", new_callable=AsyncMock) as mock_answer:
        mock_answer.return_value = _MOCK_ANSWER

        response = await async_client.post(
            "/chat",
            json={"repo_id": str(repo.id), "question": "How does connection work?"},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["answer"] == "The connect function [1] handles connections."
    assert len(data["citations"]) == 1
    cit = data["citations"][0]
    assert cit["file_path"] == "databases/backends/mysql.py"
    assert cit["function_name"] == "connect"
    assert cit["start_line"] == 10
    assert cit["end_line"] == 20
    assert cit["chunk_type"] == "function"
    assert cit["snippet"] == "def connect(): ..."


async def test_chat_nonexistent_repo_returns_404(async_client):
    response = await async_client.post(
        "/chat",
        json={"repo_id": str(uuid.uuid4()), "question": "anything"},
    )
    assert response.status_code == 404


async def test_chat_not_fully_indexed_repo_returns_400(async_client, db_session):
    repo = Repository(
        url="https://github.com/owner/running-repo",
        name="running-repo",
        status="running",
    )
    db_session.add(repo)
    await db_session.commit()

    response = await async_client.post(
        "/chat",
        json={"repo_id": str(repo.id), "question": "anything"},
    )
    assert response.status_code == 400
    assert "not fully indexed" in response.json()["detail"]


async def test_chat_empty_question_returns_422(async_client):
    response = await async_client.post(
        "/chat",
        json={"repo_id": str(uuid.uuid4()), "question": ""},
    )
    assert response.status_code == 422


async def test_chat_whitespace_question_returns_422(async_client):
    response = await async_client.post(
        "/chat",
        json={"repo_id": str(uuid.uuid4()), "question": "   "},
    )
    assert response.status_code == 422
