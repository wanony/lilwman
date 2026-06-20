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


async def test_ask_with_all_stopwords_returns_not_found(ask, mock_llm):
    # "what is the" are all stopwords; _keywords returns ""; falls back to full
    # question "what is the" which won't match anything in an empty repo
    answer = await ask.execute("what is the")
    assert answer == "Nothing in the wiki about that."
    mock_llm.generate.assert_not_called()


async def test_ask_strips_newlines_from_question_in_prompt(store, ask, mock_llm):
    await store.execute("security info topic details", ["security"], "1", "a")
    await ask.execute("security\ninfo")
    prompt = mock_llm.generate.call_args[0][0]
    # The question should be stripped of literal newlines
    assert "security\ninfo" not in prompt
    assert "security info" in prompt


async def test_ask_keywords_filters_stopwords(store, ask, mock_llm):
    await store.execute("python decorators guide", ["python"], "1", "a")
    # "what is python" → keywords = "python" → finds match
    answer = await ask.execute("what is python")
    assert answer == "Paris is the capital of France."  # mock_llm returns this
    mock_llm.generate.assert_called_once()
