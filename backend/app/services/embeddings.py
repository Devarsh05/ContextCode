import logging
import os
from abc import ABC, abstractmethod

from app.config import get_settings

logger = logging.getLogger(__name__)


class Embedder(ABC):
    @abstractmethod
    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Embed a list of texts, batching internally."""

    @abstractmethod
    def embed_query(self, text: str) -> list[float]:
        """Embed a single query string."""

    @property
    @abstractmethod
    def dimension(self) -> int: ...

    @property
    @abstractmethod
    def model_name(self) -> str: ...


class LocalEmbedder(Embedder):
    _MODEL_NAME = "all-MiniLM-L6-v2"

    def __init__(self, batch_size: int = 32) -> None:
        self.batch_size = batch_size
        self._model = None  # lazy: loaded on first embed call

    def _get_model(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer(self._MODEL_NAME)
        return self._model

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        model = self._get_model()
        results: list[list[float]] = []
        for i in range(0, len(texts), self.batch_size):
            batch = texts[i : i + self.batch_size]
            vecs = model.encode(batch, convert_to_numpy=True)
            results.extend(vecs.tolist())
        return results

    def embed_query(self, text: str) -> list[float]:
        return self.embed_texts([text])[0]

    @property
    def dimension(self) -> int:
        # Comes from the active model, never hardcoded.
        return self._get_model().get_sentence_embedding_dimension()

    @property
    def model_name(self) -> str:
        return self._MODEL_NAME


class OpenAIEmbedder(Embedder):
    _DIMENSION = 1536
    _MODEL_NAME = "text-embedding-3-small"
    # text-embedding-3-small caps inputs at 8192 tokens; stay under it with headroom.
    _MAX_INPUT_TOKENS = 8000
    _ENCODING_NAME = "cl100k_base"  # encoding used by text-embedding-3-small

    def __init__(self, batch_size: int = 100) -> None:
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise ValueError(
                "OPENAI_API_KEY environment variable is required for OpenAIEmbedder"
            )
        self._api_key = api_key
        self.batch_size = batch_size
        self._client = None  # lazy: loaded on first embed call
        self._encoding = None  # lazy: loaded on first embed call

    def _get_client(self):
        if self._client is None:
            from openai import OpenAI
            self._client = OpenAI(api_key=self._api_key)
        return self._client

    def _get_encoding(self):
        if self._encoding is None:
            import tiktoken
            self._encoding = tiktoken.get_encoding(self._ENCODING_NAME)
        return self._encoding

    def _cap_text(self, text: str, index: int) -> str:
        """Truncate a single input to the token cap so it can't fail the batch."""
        enc = self._get_encoding()
        tokens = enc.encode(text)
        if len(tokens) <= self._MAX_INPUT_TOKENS:
            return text
        logger.warning(
            "Truncating chunk %d from %d to %d tokens before OpenAI embedding",
            index,
            len(tokens),
            self._MAX_INPUT_TOKENS,
        )
        return enc.decode(tokens[: self._MAX_INPUT_TOKENS])

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        client = self._get_client()
        # Cap each input up front (global index keeps warnings pointing at the real
        # chunk) so no single oversized item can reject the whole batch.
        capped = [self._cap_text(text, i) for i, text in enumerate(texts)]
        results: list[list[float]] = []
        for i in range(0, len(capped), self.batch_size):
            batch = capped[i : i + self.batch_size]
            response = client.embeddings.create(model=self._MODEL_NAME, input=batch)
            results.extend(item.embedding for item in response.data)
        return results

    def embed_query(self, text: str) -> list[float]:
        return self.embed_texts([text])[0]

    @property
    def dimension(self) -> int:
        return self._DIMENSION

    @property
    def model_name(self) -> str:
        return self._MODEL_NAME


def get_embedder() -> Embedder:
    provider = get_settings().embedding_provider
    if provider == "openai":
        return OpenAIEmbedder()
    return LocalEmbedder()
