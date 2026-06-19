import pytest
from lilwman.application.store_entry import StoreEntryUseCase


@pytest.fixture
def use_case(repo):
    return StoreEntryUseCase(repo)


async def test_store_entry_returns_entry(use_case):
    entry = await use_case.execute(
        content="discord is cool",
        tags=["discord"],
        author_id="1",
        author_name="alice",
    )
    assert entry.id is not None
    assert entry.content == "discord is cool"
    assert entry.tags == ["discord"]


async def test_store_entry_with_no_tags(use_case):
    entry = await use_case.execute(
        content="no tags here",
        tags=[],
        author_id="1",
        author_name="alice",
    )
    assert entry.tags == []
