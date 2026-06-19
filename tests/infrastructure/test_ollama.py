from unittest.mock import AsyncMock, patch, MagicMock
import pytest
from lilwman.infrastructure.llm.ollama import OllamaLLM


async def test_generate_returns_string():
    mock_response = MagicMock()
    mock_response.response = "Paris is the capital of France."

    with patch(
        "lilwman.infrastructure.llm.ollama.ollama.AsyncClient"
    ) as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.generate = AsyncMock(return_value=mock_response)
        mock_client_cls.return_value = mock_client

        llm = OllamaLLM(host="http://localhost:11434", model="qwen2.5:1.5b")
        result = await llm.generate("What is the capital of France?")

    assert result == "Paris is the capital of France."
    mock_client.generate.assert_called_once_with(
        model="qwen2.5:1.5b",
        prompt="What is the capital of France?",
    )


async def test_generate_uses_configured_model():
    mock_response = MagicMock()
    mock_response.response = "answer"

    with patch(
        "lilwman.infrastructure.llm.ollama.ollama.AsyncClient"
    ) as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.generate = AsyncMock(return_value=mock_response)
        mock_client_cls.return_value = mock_client

        llm = OllamaLLM(host="http://localhost:11434", model="qwen2.5:0.5b")
        await llm.generate("test prompt")

    mock_client.generate.assert_called_once_with(
        model="qwen2.5:0.5b",
        prompt="test prompt",
    )
