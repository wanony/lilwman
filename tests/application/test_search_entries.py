import pytest
from lilwman.application.store_entry import StoreEntryUseCase
from lilwman.application.search_entries import SearchEntriesUseCase


@pytest.fixture
def store(repo):
    return StoreEntryUseCase(repo)


@pytest.fixture
def search(repo):
    return SearchEntriesUseCase(repo)


async def test_search_finds_content_match(store, search):
    await store.execute("python decorators explained", ["python"], "1", "a")
    await store.execute("nix flakes tutorial", ["nix"], "2", "b")
    results = await search.execute("python")
    assert len(results) == 1
    assert "python" in results[0].content


async def test_search_finds_tag_match(store, search):
    await store.execute("some content", ["nix", "flakes"], "1", "a")
    results = await search.execute("flakes")
    assert len(results) == 1


async def test_search_returns_empty_for_no_match(store, search):
    await store.execute("irrelevant content", ["misc"], "1", "a")
    results = await search.execute("zzznomatch")
    assert results == []


async def test_search_returns_multiple_ranked_results(store, search):
    await store.execute("python is great for scripting", ["python"], "1", "a")
    await store.execute("python also works for web", ["python", "web"], "2", "b")
    await store.execute("javascript for web", ["js"], "3", "c")
    results = await search.execute("python")
    assert len(results) == 2


async def test_search_respects_limit_of_20(store, search):
    for i in range(21):
        await store.execute(f"python entry number {i}", ["python"], str(i), f"user{i}")
    results = await search.execute("python")
    assert len(results) == 20


async def test_search_empty_query_returns_empty(search):
    results = await search.execute("")
    assert results == []
