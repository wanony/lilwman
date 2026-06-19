from unittest.mock import AsyncMock
import pytest
from lilwman.application.store_entry import StoreEntryUseCase
from lilwman.application.ask_query import AskQueryUseCase


@pytest.fixture
def store(repo):
    return StoreEntryUseCase(repo)


@pytest.fixture
def mock_llm():
    llm = AsyncMock()
    llm.generate = AsyncMock(return_value="Paris is the capital of France.")
    return llm


@pytest.fixture
def ask(repo, mock_llm):
    return AskQueryUseCase(repo, mock_llm)


async def test_ask_returns_llm_answer_when_results_found(store, ask, mock_llm):
    await store.execute("France capital is Paris", ["geography"], "1", "a")
    answer = await ask.execute("France capital")
    assert answer == "Paris is the capital of France."
    mock_llm.generate.assert_called_once()


async def test_ask_returns_not_found_when_no_wiki_entries(ask, mock_llm):
    answer = await ask.execute("internet invented")
    assert answer == "Nothing in the wiki about that."
    mock_llm.generate.assert_not_called()


async def test_ask_prompt_includes_wiki_entries(store, ask, mock_llm):
    await store.execute("The sky is blue", ["science"], "1", "a")
    await ask.execute("sky blue")
    prompt = mock_llm.generate.call_args[0][0]
    assert "The sky is blue" in prompt
    assert "sky blue" in prompt
