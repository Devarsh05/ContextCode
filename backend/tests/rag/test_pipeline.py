import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.rag.pipeline import Citation, RAGPipeline
from app.services.embeddings import Embedder
from app.services.llm import LLMClient
from app.services.vector_store import VectorStore


def _make_chunk(n: int) -> dict:
    return {
        "chunk_id": f"chunk-{n}",
        "content": f"def func_{n}(): pass",
        "metadata": {
            "file_path": f"app/module_{n}.py",
            "chunk_type": "function",
            "function_name": f"func_{n}",
            "start_line": n * 10,
            "end_line": n * 10 + 5,
            "language": "python",
        },
        "distance": 0.1 * n,
    }


@pytest.fixture
def embedder():
    mock = MagicMock(spec=Embedder)
    mock.embed_query.return_value = [0.1] * 384
    return mock


@pytest.fixture
def vector_store():
    mock = MagicMock(spec=VectorStore)
    mock.query.return_value = [_make_chunk(1), _make_chunk(2)]
    return mock


@pytest.fixture
def llm_client():
    mock = AsyncMock(spec=LLMClient)
    mock.generate.return_value = json.dumps({"answer": "see [1]", "cited_chunks": [1]})
    return mock


@pytest.fixture
def pipeline(embedder, vector_store, llm_client):
    return RAGPipeline(embedder=embedder, vector_store=vector_store, llm_client=llm_client)


class TestRAGPipelineAnswer:
    @pytest.mark.asyncio
    async def test_embed_called_with_question(self, pipeline, embedder):
        await pipeline.answer(repo_id="repo-1", question="What does func_1 do?")
        embedder.embed_query.assert_called_once_with("What does func_1 do?")

    @pytest.mark.asyncio
    async def test_vector_store_called_with_repo_id_and_top_k(self, pipeline, vector_store):
        await pipeline.answer(repo_id="repo-1", question="What does func_1 do?")
        vector_store.query.assert_called_once_with("repo-1", [0.1] * 384, 8)

    @pytest.mark.asyncio
    async def test_prompt_contains_all_retrieved_chunks(self, pipeline, llm_client):
        await pipeline.answer(repo_id="repo-1", question="What does func_1 do?")
        call_kwargs = llm_client.generate.call_args.kwargs
        user_msg = call_kwargs["user"]
        assert "[1]" in user_msg
        assert "[2]" in user_msg
        assert "def func_1(): pass" in user_msg
        assert "def func_2(): pass" in user_msg

    @pytest.mark.asyncio
    async def test_citations_parsed_from_llm_response(self, pipeline, llm_client):
        llm_client.generate.return_value = json.dumps({
            "answer": "func_1 does X [1]",
            "cited_chunks": [1],
        })
        result = await pipeline.answer(repo_id="repo-1", question="What does func_1 do?")
        assert result["answer"] == "func_1 does X [1]"
        assert len(result["citations"]) == 1
        citation = result["citations"][0]
        assert isinstance(citation, Citation)
        assert citation.file_path == "app/module_1.py"
        assert citation.function_name == "func_1"
        assert citation.start_line == 10
        assert citation.end_line == 15
        assert citation.chunk_type == "function"
        assert citation.snippet == "def func_1(): pass"

    @pytest.mark.asyncio
    async def test_empty_retrieval_returns_graceful_message(self, pipeline, vector_store):
        vector_store.query.return_value = []
        result = await pipeline.answer(repo_id="repo-1", question="anything")
        assert "I don't have enough context" in result["answer"]
        assert result["citations"] == []

    @pytest.mark.asyncio
    async def test_out_of_range_chunk_numbers_ignored(self, pipeline, llm_client):
        llm_client.generate.return_value = json.dumps({
            "answer": "hallucinated [99]",
            "cited_chunks": [99],
        })
        result = await pipeline.answer(repo_id="repo-1", question="anything")
        assert result["citations"] == []

    @pytest.mark.asyncio
    async def test_json_parse_failure_raises_value_error(self, pipeline, llm_client):
        llm_client.generate.return_value = "not valid json {{"
        with pytest.raises(ValueError, match="non-JSON"):
            await pipeline.answer(repo_id="repo-1", question="anything")
