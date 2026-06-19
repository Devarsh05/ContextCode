import os
from abc import ABC, abstractmethod

from app.config import get_settings


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

    def __init__(self, batch_size: int = 100) -> None:
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise ValueError(
                "OPENAI_API_KEY environment variable is required for OpenAIEmbedder"
            )
        self._api_key = api_key
        self.batch_size = batch_size
        self._client = None  # lazy: loaded on first embed call

    def _get_client(self):
        if self._client is None:
            from openai import OpenAI
            self._client = OpenAI(api_key=self._api_key)
        return self._client

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        client = self._get_client()
        results: list[list[float]] = []
        for i in range(0, len(texts), self.batch_size):
            batch = texts[i : i + self.batch_size]
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
