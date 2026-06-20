import os
import uuid
from dataclasses import dataclass
from unittest.mock import patch

import pytest

from app.services.vector_store import VectorStore


@pytest.fixture(autouse=True)
def _force_local_chroma():
    """Force the embedded PersistentClient path on tmp_path regardless of the
    developer's local .env. create_chroma_client() reads CHROMA_HOST live via the
    uncached get_settings(); the test process inherits .env through
    app.models.database's import-time load_dotenv(). Setting CHROMA_HOST="" (falsy)
    keeps every test on an isolated on-disk client instead of a shared HttpClient."""
    with patch.dict(os.environ, {"CHROMA_HOST": ""}):
        yield


@dataclass
class FakeChunk:
    id: str
    file_path: str
    chunk_type: str
    function_name: str | None
    start_line: int
    end_line: int
    content: str
    language: str


def _make_chunk(n: int, chunk_type: str = "function") -> FakeChunk:
    return FakeChunk(
        id=str(uuid.uuid4()),
        file_path=f"src/file_{n}.py",
        chunk_type=chunk_type,
        function_name=f"func_{n}" if chunk_type != "module" else None,
        start_line=n * 10,
        end_line=n * 10 + 9,
        content=f"def func_{n}(): pass",
        language="python",
    )


# 3-D embeddings keep tests fast and deterministic (no real model needed).
# L2 distance: [1,0,0] vs [1,0,0] → 0; vs [0,1,0] → sqrt(2).
_VEC_A = [1.0, 0.0, 0.0]
_VEC_B = [0.0, 1.0, 0.0]
_VEC_C = [0.0, 0.0, 1.0]


class TestAddAndQuery:
    def test_add_then_query_returns_chunks_ranked_by_similarity(self, tmp_path):
        store = VectorStore(persist_path=str(tmp_path))
        chunk_a = _make_chunk(1)
        chunk_b = _make_chunk(2)
        store.add_chunks(1, [chunk_a, chunk_b], [_VEC_A, _VEC_B])

        results = store.query(1, _VEC_A, top_k=2)

        assert len(results) == 2
        # Closest match (distance 0) should be chunk_a.
        assert results[0]["chunk_id"] == chunk_a.id
        assert results[0]["content"] == chunk_a.content
        assert results[0]["distance"] < results[1]["distance"]

    def test_query_result_metadata_contains_expected_fields(self, tmp_path):
        store = VectorStore(persist_path=str(tmp_path))
        chunk = _make_chunk(1)
        store.add_chunks(1, [chunk], [_VEC_A])

        results = store.query(1, _VEC_A, top_k=1)

        assert len(results) == 1
        meta = results[0]["metadata"]
        assert meta["file_path"] == chunk.file_path
        assert meta["chunk_type"] == chunk.chunk_type
        assert meta["language"] == chunk.language
        assert meta["start_line"] == chunk.start_line
        assert meta["end_line"] == chunk.end_line

    def test_query_empty_collection_returns_empty_list(self, tmp_path):
        store = VectorStore(persist_path=str(tmp_path))
        results = store.query(1, _VEC_A, top_k=5)
        assert results == []

    def test_query_top_k_larger_than_count_returns_all(self, tmp_path):
        store = VectorStore(persist_path=str(tmp_path))
        chunk = _make_chunk(1)
        store.add_chunks(1, [chunk], [_VEC_A])

        results = store.query(1, _VEC_A, top_k=100)

        assert len(results) == 1

    def test_module_chunk_with_none_function_name_stored_and_returned(self, tmp_path):
        store = VectorStore(persist_path=str(tmp_path))
        chunk = _make_chunk(1, chunk_type="module")
        assert chunk.function_name is None
        store.add_chunks(1, [chunk], [_VEC_A])

        results = store.query(1, _VEC_A, top_k=1)

        assert len(results) == 1
        assert results[0]["chunk_id"] == chunk.id


class TestDropCollection:
    def test_drop_collection_removes_all_chunks(self, tmp_path):
        store = VectorStore(persist_path=str(tmp_path))
        store.add_chunks(1, [_make_chunk(1)], [_VEC_A])
        assert store.chunk_count(1) == 1

        store.drop_collection(1)

        assert store.chunk_count(1) == 0

    def test_drop_nonexistent_collection_does_not_raise(self, tmp_path):
        store = VectorStore(persist_path=str(tmp_path))
        store.drop_collection(999)  # must not raise

    def test_drop_collection_leaves_other_repos_intact(self, tmp_path):
        store = VectorStore(persist_path=str(tmp_path))
        store.add_chunks(1, [_make_chunk(1)], [_VEC_A])
        store.add_chunks(2, [_make_chunk(2)], [_VEC_B])

        store.drop_collection(1)

        assert store.chunk_count(1) == 0
        assert store.chunk_count(2) == 1


class TestIsolation:
    def test_two_repo_ids_stay_isolated(self, tmp_path):
        store = VectorStore(persist_path=str(tmp_path))
        chunk_1 = _make_chunk(1)
        chunk_2 = _make_chunk(2)
        store.add_chunks(1, [chunk_1], [_VEC_A])
        store.add_chunks(2, [chunk_2], [_VEC_B])

        results = store.query(1, _VEC_A, top_k=5)
        ids_in_repo1 = {r["chunk_id"] for r in results}

        assert chunk_1.id in ids_in_repo1
        assert chunk_2.id not in ids_in_repo1

    def test_repo1_count_unaffected_by_repo2_additions(self, tmp_path):
        store = VectorStore(persist_path=str(tmp_path))
        store.add_chunks(1, [_make_chunk(1)], [_VEC_A])
        store.add_chunks(2, [_make_chunk(2), _make_chunk(3)], [_VEC_B, _VEC_C])

        assert store.chunk_count(1) == 1
        assert store.chunk_count(2) == 2


class TestChunkCount:
    def test_chunk_count_accurate_after_add(self, tmp_path):
        store = VectorStore(persist_path=str(tmp_path))
        chunks = [_make_chunk(i) for i in range(5)]
        embeddings = [[float(i), 0.0, 0.0] for i in range(5)]
        store.add_chunks(1, chunks, embeddings)

        assert store.chunk_count(1) == 5

    def test_chunk_count_zero_for_empty_collection(self, tmp_path):
        store = VectorStore(persist_path=str(tmp_path))
        assert store.chunk_count(1) == 0


class TestGetOrCreateCollection:
    def test_get_or_create_collection_name_matches_repo_id(self, tmp_path):
        store = VectorStore(persist_path=str(tmp_path))
        collection = store.get_or_create_collection(42)
        assert collection.name == "repo_42"

    def test_get_or_create_collection_is_idempotent(self, tmp_path):
        store = VectorStore(persist_path=str(tmp_path))
        col1 = store.get_or_create_collection(1)
        col2 = store.get_or_create_collection(1)
        assert col1.name == col2.name
