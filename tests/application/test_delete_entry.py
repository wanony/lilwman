import pytest
from lilwman.application.store_entry import StoreEntryUseCase
from lilwman.application.delete_entry import DeleteEntryUseCase


@pytest.fixture
def store(repo):
    return StoreEntryUseCase(repo)


@pytest.fixture
def delete(repo):
    return DeleteEntryUseCase(repo)


async def test_delete_own_entry(store, delete):
    entry = await store.execute("my entry", [], "111", "alice")
    result = await delete.execute(entry.id, author_id="111", is_admin=False)
    assert result is True


async def test_delete_other_entry_denied(store, delete):
    entry = await store.execute("your entry", [], "999", "bob")
    result = await delete.execute(entry.id, author_id="111", is_admin=False)
    assert result is False


async def test_delete_any_entry_as_admin(store, delete):
    entry = await store.execute("anyone's entry", [], "999", "bob")
    result = await delete.execute(entry.id, author_id="111", is_admin=True)
    assert result is True


async def test_delete_nonexistent_entry_returns_false(delete):
    result = await delete.execute(9999, author_id="111", is_admin=True)
    assert result is False
