import ollama

from lilwman.domain.ports import LLMPort

_TIMEOUT_SECONDS = 120


class OllamaLLM(LLMPort):
    def __init__(self, host: str, model: str) -> None:
        self._model = model
        self._client = ollama.AsyncClient(host=host, timeout=_TIMEOUT_SECONDS)

    async def generate(self, prompt: str) -> str:
        response = await self._client.generate(model=self._model, prompt=prompt)
        return response.response
