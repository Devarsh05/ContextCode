import asyncio
import json
import logging
from dataclasses import dataclass

from app.services.embeddings import Embedder, get_embedder
from app.services.llm import LLMClient, get_llm_client
from app.services.vector_store import VectorStore, get_vector_store

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = (
    "You are an expert code assistant helping developers understand a codebase.\n\n"
    "You will be given numbered context blocks, each containing a code snippet from the "
    "codebase with its file location. Answer the user's question using ONLY the information "
    "in these context blocks.\n\n"
    "If the provided context is insufficient to answer the question, say so directly — "
    "do not infer or guess based on knowledge outside the provided chunks.\n\n"
    "When referencing specific code, cite the chunk number using [N] notation inline in your answer.\n\n"
    "You MUST respond with valid JSON in exactly this format:\n"
    '{\n  "answer": "your full answer here, using [1], [2], etc. inline to cite chunks",\n'
    '  "cited_chunks": [1, 2]\n}\n\n'
    '"cited_chunks" must be a JSON array of integers (the chunk numbers you cited). '
    "If you cited no chunks, use an empty array []."
)


@dataclass
class Citation:
    file_path: str
    function_name: str
    start_line: int
    end_line: int
    chunk_type: str
    snippet: str


class RAGPipeline:
    def __init__(
        self,
        embedder: Embedder | None = None,
        vector_store: VectorStore | None = None,
        llm_client: LLMClient | None = None,
        top_k: int = 8,
    ) -> None:
        self._embedder = embedder or get_embedder()
        self._vector_store = vector_store or get_vector_store()
        self._llm_client = llm_client or get_llm_client()
        self._top_k = top_k

    async def answer(self, repo_id: str, question: str) -> dict:
        loop = asyncio.get_running_loop()

        embedding: list[float] = await loop.run_in_executor(
            None, self._embedder.embed_query, question
        )

        retrieved: list[dict] = await loop.run_in_executor(
            None, lambda: self._vector_store.query(repo_id, embedding, self._top_k)
        )

        if not retrieved:
            return {
                "answer": (
                    "I don't have enough context to answer that question. "
                    "The repository may not be indexed yet, or the question "
                    "may not relate to any code in this codebase."
                ),
                "citations": [],
            }

        context = _build_context(retrieved)
        raw = await self._llm_client.generate(
            system=_SYSTEM_PROMPT,
            user=f"Context:\n{context}\n\nQuestion: {question}",
            max_tokens=1024,
        )
        return _parse_response(raw, retrieved)


def _build_context(retrieved: list[dict]) -> str:
    blocks = []
    for n, chunk in enumerate(retrieved, start=1):
        meta = chunk["metadata"]
        header = (
            f"[{n}] {meta['file_path']}:{meta['start_line']}-{meta['end_line']}"
            f" ({meta['chunk_type']})"
        )
        block = f"{header}\n```\n{chunk['content']}\n```"
        blocks.append(block)
    return "\n\n".join(blocks)


def _parse_response(raw: str, retrieved: list[dict]) -> dict:
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"LLM returned non-JSON response: {raw!r}") from exc

    answer = parsed.get("answer", "")
    cited_indices = parsed.get("cited_chunks", [])

    citations: list[Citation] = []
    for n in cited_indices:
        if not isinstance(n, int):
            continue
        idx = n - 1
        if idx < 0 or idx >= len(retrieved):
            continue
        chunk = retrieved[idx]
        meta = chunk["metadata"]
        citations.append(
            Citation(
                file_path=meta["file_path"],
                function_name=meta.get("function_name", ""),
                start_line=meta["start_line"],
                end_line=meta["end_line"],
                chunk_type=meta["chunk_type"],
                snippet=chunk["content"],
            )
        )

    return {"answer": answer, "citations": citations}
