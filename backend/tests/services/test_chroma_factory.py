"""Chroma client factory selection (no live server — clients are mocked)."""

import os
from unittest.mock import MagicMock, patch

from app.services import vector_store


def _clear_chroma_env() -> dict:
    return {k: v for k, v in os.environ.items() if not k.startswith("CHROMA_")}


class TestCreateChromaClient:
    def test_returns_http_client_when_chroma_host_set(self):
        env = _clear_chroma_env()
        env.update({"CHROMA_HOST": "chroma.internal", "CHROMA_PORT": "9000"})
        with patch.dict(os.environ, env, clear=True):
            with patch.object(vector_store.chromadb, "HttpClient") as http, \
                 patch.object(vector_store.chromadb, "PersistentClient") as persistent:
                client = vector_store.create_chroma_client("./chroma_data")

        persistent.assert_not_called()
        http.assert_called_once()
        kwargs = http.call_args.kwargs
        assert kwargs["host"] == "chroma.internal"
        assert kwargs["port"] == 9000
        # No token → no Authorization header.
        assert kwargs["headers"] is None
        assert client is http.return_value

    def test_http_client_sends_bearer_header_when_token_set(self):
        env = _clear_chroma_env()
        env.update(
            {"CHROMA_HOST": "chroma.internal", "CHROMA_TOKEN": "secret-token"}
        )
        with patch.dict(os.environ, env, clear=True):
            with patch.object(vector_store.chromadb, "HttpClient") as http, \
                 patch.object(vector_store.chromadb, "PersistentClient"):
                vector_store.create_chroma_client("./chroma_data")

        assert http.call_args.kwargs["headers"] == {
            "Authorization": "Bearer secret-token"
        }

    def test_returns_persistent_client_when_no_chroma_host(self):
        env = _clear_chroma_env()  # CHROMA_HOST absent
        with patch.dict(os.environ, env, clear=True):
            with patch.object(vector_store.chromadb, "HttpClient") as http, \
                 patch.object(vector_store.chromadb, "PersistentClient") as persistent:
                client = vector_store.create_chroma_client("/tmp/data")

        http.assert_not_called()
        persistent.assert_called_once_with(path="/tmp/data")
        assert client is persistent.return_value
