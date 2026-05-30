import os
from abc import ABC, abstractmethod

from openai import AsyncOpenAI


class LLMClient(ABC):
    @abstractmethod
    async def generate(self, system: str, user: str, max_tokens: int = 1024) -> str:
        """Call the LLM and return the raw response string."""

    @property
    @abstractmethod
    def model_name(self) -> str: ...


class OpenAIClient(LLMClient):
    def __init__(self) -> None:
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise ValueError(
                "OPENAI_API_KEY environment variable is required for OpenAIClient"
            )
        self._api_key = api_key
        self._model_name = os.environ.get("LLM_MODEL", "gpt-4o-mini")
        self._client: AsyncOpenAI | None = None

    def _get_client(self) -> AsyncOpenAI:
        if self._client is None:
            self._client = AsyncOpenAI(api_key=self._api_key)
        return self._client

    async def generate(self, system: str, user: str, max_tokens: int = 1024) -> str:
        client = self._get_client()
        response = await client.chat.completions.create(
            model=self._model_name,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            max_tokens=max_tokens,
            response_format={"type": "json_object"},
        )
        return response.choices[0].message.content

    @property
    def model_name(self) -> str:
        return self._model_name


def get_llm_client() -> LLMClient:
    provider = os.environ.get("LLM_PROVIDER", "openai")
    if provider == "openai":
        return OpenAIClient()
    raise ValueError(f"Unknown LLM_PROVIDER: {provider!r}")
