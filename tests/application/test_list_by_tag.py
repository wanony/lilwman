import pytest
from lilwman.application.store_entry import StoreEntryUseCase
from lilwman.application.list_by_tag import ListByTagUseCase


@pytest.fixture
def store(repo):
    return StoreEntryUseCase(repo)


@pytest.fixture
def list_tag(repo):
    return ListByTagUseCase(repo)


async def test_list_by_tag_returns_matching(store, list_tag):
    await store.execute("entry a", ["alpha"], "1", "a")
    await store.execute("entry b", ["alpha", "beta"], "2", "b")
    await store.execute("entry c", ["gamma"], "3", "c")
    results = await list_tag.execute("alpha")
    assert len(results) == 2


async def test_list_by_tag_empty_for_no_match(list_tag):
    results = await list_tag.execute("nonexistent")
    assert results == []


async def test_list_by_tag_ordered_by_creation(store, list_tag):
    entry1 = await store.execute("first", ["tag"], "1", "a")
    entry2 = await store.execute("second", ["tag"], "2", "b")
    entry3 = await store.execute("third", ["tag"], "3", "c")
    results = await list_tag.execute("tag")
    assert len(results) == 3
    assert [r.id for r in results] == [entry3.id, entry2.id, entry1.id]
