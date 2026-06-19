import ollama

from lilwman.domain.ports import LLMPort


class OllamaLLM(LLMPort):
    def __init__(self, host: str, model: str) -> None:
        self._host = host
        self._model = model

    async def generate(self, prompt: str) -> str:
        client = ollama.AsyncClient(host=self._host)
        response = await client.generate(model=self._model, prompt=prompt)
        return response.response
