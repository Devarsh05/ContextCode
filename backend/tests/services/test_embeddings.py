import os
import subprocess
import sys
import textwrap
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
# Dimension comes from the active provider — never hardcoded at the call site.
# ---------------------------------------------------------------------------

class TestEmbedderDimension:
    def test_local_dimension_reported_by_model(self):
        # all-MiniLM-L6-v2 → 384, read from the loaded model (not a constant).
        assert LocalEmbedder().dimension == 384

    def test_openai_dimension(self):
        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test"}):
            # text-embedding-3-small → 1536, no API call needed.
            assert OpenAIEmbedder().dimension == 1536


# ---------------------------------------------------------------------------
# Lazy-import guard: the production image installs base requirements WITHOUT
# torch/sentence-transformers. The app must import and the OpenAI embedder must
# work even when those packages are absent. Run in a subprocess so the blocked
# modules don't pollute this test session.
# ---------------------------------------------------------------------------

class TestLazyImportGuard:
    def test_app_imports_with_provider_openai_and_torch_absent(self):
        script = textwrap.dedent(
            """
            import sys
            # Setting a module to None makes `import <name>` raise ImportError,
            # simulating the torch-free production image.
            sys.modules["torch"] = None
            sys.modules["sentence_transformers"] = None

            import app.main  # full import graph must not pull in torch
            from app.services.embeddings import get_embedder, OpenAIEmbedder

            embedder = get_embedder()
            assert isinstance(embedder, OpenAIEmbedder), type(embedder)
            assert sys.modules.get("sentence_transformers") is None
            print("OK")
            """
        )
        env = {
            **os.environ,
            "EMBEDDING_PROVIDER": "openai",
            "OPENAI_API_KEY": "sk-test",
            "DATABASE_URL": "sqlite+aiosqlite:///:memory:",
            "REDIS_URL": "redis://localhost:6379/0",
        }
        result = subprocess.run(
            [sys.executable, "-c", script],
            cwd=os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            env=env,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, f"stdout={result.stdout}\nstderr={result.stderr}"
        assert "OK" in result.stdout


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

    def test_cap_text_truncates_over_cap_input(self):
        import tiktoken

        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test"}):
            embedder = OpenAIEmbedder()

        enc = tiktoken.get_encoding("cl100k_base")
        # " word" is a single token; repeat well past the cap.
        text = " word" * (OpenAIEmbedder._MAX_INPUT_TOKENS + 500)
        assert len(enc.encode(text)) > OpenAIEmbedder._MAX_INPUT_TOKENS

        capped = embedder._cap_text(text, 68)
        assert len(enc.encode(capped)) <= OpenAIEmbedder._MAX_INPUT_TOKENS

    def test_cap_text_leaves_normal_input_unchanged(self):
        import tiktoken

        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test"}):
            embedder = OpenAIEmbedder()

        enc = tiktoken.get_encoding("cl100k_base")
        text = "def add(a, b):\n    return a + b\n"
        assert len(enc.encode(text)) < OpenAIEmbedder._MAX_INPUT_TOKENS

        assert embedder._cap_text(text, 0) == text
