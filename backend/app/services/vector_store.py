"""ChromaDB storage layer.

One collection per repo, named ``repo_{repo_id}``. All methods are
synchronous — this module is called from the Celery worker, not from
async endpoints (see CLAUDE.md).

Production callers should use ``get_vector_store()`` to obtain the
process-wide singleton rather than constructing ``VectorStore`` directly.
"""

import logging
from typing import Any

import chromadb
from chromadb import Collection

logger = logging.getLogger(__name__)

_store: "VectorStore | None" = None


class VectorStore:
    def __init__(self, persist_path: str = "./chroma_data") -> None:
        self._persist_path = persist_path
        self._client: chromadb.PersistentClient | None = None

    def _get_client(self) -> chromadb.PersistentClient:
        if self._client is None:
            self._client = chromadb.PersistentClient(path=self._persist_path)
        return self._client

    def get_or_create_collection(self, repo_id: int) -> Collection:
        return self._get_client().get_or_create_collection(f"repo_{repo_id}")

    def add_chunks(
        self,
        repo_id: int,
        chunks: list[Any],
        embeddings: list[list[float]],
    ) -> None:
        """Store chunks with pre-computed embeddings in the repo's collection.

        ``chunk.id`` becomes the Chroma document id. ``chunk.function_name``
        is stored as an empty string when None because ChromaDB metadata
        values must be str/int/float/bool.
        """
        collection = self.get_or_create_collection(repo_id)
        collection.add(
            ids=[str(chunk.id) for chunk in chunks],
            documents=[chunk.content for chunk in chunks],
            embeddings=embeddings,
            metadatas=[
                {
                    "file_path": chunk.file_path,
                    "chunk_type": chunk.chunk_type,
                    "function_name": chunk.function_name or "",
                    "start_line": chunk.start_line,
                    "end_line": chunk.end_line,
                    "language": chunk.language,
                }
                for chunk in chunks
            ],
        )

    def query(
        self,
        repo_id: int,
        query_embedding: list[float],
        top_k: int = 5,
    ) -> list[dict]:
        """Return up to ``top_k`` chunks nearest to ``query_embedding``.

        Each dict has keys: chunk_id, content, metadata, distance.
        Returns [] when the collection is empty.
        """
        collection = self.get_or_create_collection(repo_id)
        count = collection.count()
        if count == 0:
            return []
        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=min(top_k, count),
            include=["documents", "metadatas", "distances"],
        )
        return [
            {
                "chunk_id": results["ids"][0][i],
                "content": results["documents"][0][i],
                "metadata": results["metadatas"][0][i],
                "distance": results["distances"][0][i],
            }
            for i in range(len(results["ids"][0]))
        ]

    def drop_collection(self, repo_id: int) -> None:
        """Delete the collection for ``repo_id``. No-op if it doesn't exist."""
        try:
            self._get_client().delete_collection(f"repo_{repo_id}")
        except Exception:
            logger.debug("Collection repo_%s not found; nothing to drop", repo_id)

    def chunk_count(self, repo_id: int) -> int:
        return self.get_or_create_collection(repo_id).count()


def get_vector_store() -> VectorStore:
    """Return the process-wide singleton VectorStore."""
    global _store
    if _store is None:
        _store = VectorStore()
    return _store
