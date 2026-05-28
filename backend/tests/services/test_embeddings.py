import os
from unittest.mock import MagicMock, patch

import pytest

from app.services.embeddings import Embedder, LocalEmbedder, OpenAIEmbedder, get_embedder


# ---------------------------------------------------------------------------
# LocalEmbedder — downloads the model on first run (~90 MB), then cached.
# Collection is instant because the model is lazy-loaded, not imported.
# ---------------------------------------------------------------------------

class TestLocalEmbedder:
    def test_local_embed_query_returns_correct_dimension(self):
        embedder = LocalEmbedder()
        result = embedder.embed_query("hello world")
        assert isinstance(result, list)
        assert len(result) == 384
        assert all(isinstance(v, float) for v in result)

    def test_local_embed_texts_batch_shape(self):
        embedder = LocalEmbedder()
        texts = ["hello", "world", "foo bar"]
        results = embedder.embed_texts(texts)
        assert len(results) == 3
        assert all(len(vec) == 384 for vec in results)

    def test_local_embed_query_consistent_with_embed_texts(self):
        embedder = LocalEmbedder()
        text = "consistency check"
        assert embedder.embed_query(text) == embedder.embed_texts([text])[0]

    def test_local_determinism(self):
        embedder = LocalEmbedder()
        text = "determinism check"
        assert embedder.embed_query(text) == embedder.embed_query(text)


# ---------------------------------------------------------------------------
# get_embedder() factory
# ---------------------------------------------------------------------------

class TestGetEmbedder:
    def test_get_embedder_default_is_local(self):
        env = {k: v for k, v in os.environ.items() if k != "EMBEDDING_PROVIDER"}
        with patch.dict(os.environ, env, clear=True):
            embedder = get_embedder()
        assert isinstance(embedder, LocalEmbedder)

    def test_get_embedder_explicit_local(self):
        with patch.dict(os.environ, {"EMBEDDING_PROVIDER": "local"}):
            embedder = get_embedder()
        assert isinstance(embedder, LocalEmbedder)

    def test_get_embedder_openai(self):
        with patch.dict(os.environ, {"EMBEDDING_PROVIDER": "openai", "OPENAI_API_KEY": "sk-test"}):
            embedder = get_embedder()
        assert isinstance(embedder, OpenAIEmbedder)


# ---------------------------------------------------------------------------
# OpenAIEmbedder — client is mocked; no real API calls made
# ---------------------------------------------------------------------------

class TestOpenAIEmbedder:
    def test_openai_raises_if_api_key_missing(self):
        env = {k: v for k, v in os.environ.items() if k != "OPENAI_API_KEY"}
        with patch.dict(os.environ, env, clear=True):
            with pytest.raises(ValueError, match="OPENAI_API_KEY"):
                OpenAIEmbedder()

    def test_openai_embed_texts_batches_api_calls(self):
        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test"}):
            embedder = OpenAIEmbedder(batch_size=2)

        # Inject a mock client so no real HTTP occurs
        mock_client = MagicMock()
        embedder._client = mock_client

        def _make_response(n: int):
            resp = MagicMock()
            resp.data = [MagicMock(embedding=[0.1] * 1536) for _ in range(n)]
            return resp

        mock_client.embeddings.create.side_effect = [
            _make_response(2),  # first batch: texts[0:2]
            _make_response(1),  # second batch: texts[2:3]
        ]

        results = embedder.embed_texts(["a", "b", "c"])
        assert len(results) == 3
        assert mock_client.embeddings.create.call_count == 2
