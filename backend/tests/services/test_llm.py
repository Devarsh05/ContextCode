import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.llm import LLMClient, OpenAIClient, get_llm_client


class TestOpenAIClient:
    def test_raises_if_api_key_missing(self):
        env = {k: v for k, v in os.environ.items() if k != "OPENAI_API_KEY"}
        with patch.dict(os.environ, env, clear=True):
            with pytest.raises(ValueError, match="OPENAI_API_KEY"):
                OpenAIClient()

    @pytest.mark.asyncio
    async def test_generate_calls_api_with_correct_shape(self):
        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test"}):
            client = OpenAIClient()

        mock_response = MagicMock()
        mock_response.choices = [
            MagicMock(message=MagicMock(content='{"answer": "hi", "cited_chunks": []}'))
        ]
        mock_openai = AsyncMock()
        mock_openai.chat.completions.create = AsyncMock(return_value=mock_response)
        client._client = mock_openai

        result = await client.generate(system="sys prompt", user="user msg", max_tokens=512)

        assert result == '{"answer": "hi", "cited_chunks": []}'
        call_kwargs = mock_openai.chat.completions.create.call_args.kwargs
        assert call_kwargs["messages"] == [
            {"role": "system", "content": "sys prompt"},
            {"role": "user", "content": "user msg"},
        ]
        assert call_kwargs["max_tokens"] == 512
        assert call_kwargs["response_format"] == {"type": "json_object"}

    def test_model_name_from_env(self):
        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test", "LLM_MODEL": "gpt-4o"}):
            client = OpenAIClient()
        assert client.model_name == "gpt-4o"

    def test_model_name_default(self):
        env = {k: v for k, v in os.environ.items() if k != "LLM_MODEL"}
        env["OPENAI_API_KEY"] = "sk-test"
        with patch.dict(os.environ, env, clear=True):
            client = OpenAIClient()
        assert client.model_name == "gpt-4o-mini"


class TestGetLLMClient:
    def test_returns_openai_client_by_default(self):
        env = {k: v for k, v in os.environ.items() if k != "LLM_PROVIDER"}
        env["OPENAI_API_KEY"] = "sk-test"
        with patch.dict(os.environ, env, clear=True):
            client = get_llm_client()
        assert isinstance(client, OpenAIClient)

    def test_returns_openai_client_explicit(self):
        with patch.dict(os.environ, {"LLM_PROVIDER": "openai", "OPENAI_API_KEY": "sk-test"}):
            client = get_llm_client()
        assert isinstance(client, OpenAIClient)

    def test_raises_for_unknown_provider(self):
        with patch.dict(os.environ, {"LLM_PROVIDER": "anthropic"}):
            with pytest.raises(ValueError, match="anthropic"):
                get_llm_client()
