import pytest
from lilwman.infrastructure.db.repository import SQLAlchemyEntryRepository


@pytest.fixture
def repo(session_factory):
    return SQLAlchemyEntryRepository(session_factory)


async def test_save_returns_entry_with_id(repo):
    entry = await repo.save(
        content="hello world",
        tags=["greet"],
        author_id="111",
        author_name="alice",
    )
    assert entry.id is not None
    assert entry.content == "hello world"
    assert entry.tags == ["greet"]
    assert entry.author_id == "111"


async def test_get_by_id_returns_saved_entry(repo):
    saved = await repo.save(
        content="nix is great",
        tags=["nix"],
        author_id="222",
        author_name="bob",
    )
    fetched = await repo.get_by_id(saved.id)
    assert fetched is not None
    assert fetched.id == saved.id
    assert fetched.content == "nix is great"
    assert fetched.tags == ["nix"]


async def test_get_by_id_returns_none_for_missing(repo):
    result = await repo.get_by_id(9999)
    assert result is None


async def test_search_finds_matching_entry(repo):
    await repo.save(content="python is fun", tags=["python"], author_id="1", author_name="a")
    await repo.save(content="nix flakes rock", tags=["nix"], author_id="2", author_name="b")
    results = await repo.search("python")
    assert len(results) == 1
    assert results[0].content == "python is fun"


async def test_search_returns_empty_for_no_match(repo):
    await repo.save(content="unrelated stuff", tags=[], author_id="1", author_name="a")
    results = await repo.search("zzznomatch")
    assert results == []


async def test_list_by_tag_returns_entries_with_tag(repo):
    await repo.save(content="entry one", tags=["alpha", "beta"], author_id="1", author_name="a")
    await repo.save(content="entry two", tags=["beta"], author_id="2", author_name="b")
    await repo.save(content="entry three", tags=["gamma"], author_id="3", author_name="c")
    results = await repo.list_by_tag("beta")
    assert len(results) == 2


async def test_delete_own_entry_succeeds(repo):
    entry = await repo.save(content="to delete", tags=[], author_id="111", author_name="me")
    deleted = await repo.delete(entry.id, author_id="111", is_admin=False)
    assert deleted is True
    assert await repo.get_by_id(entry.id) is None


async def test_delete_other_entry_fails_without_admin(repo):
    entry = await repo.save(content="not mine", tags=[], author_id="999", author_name="other")
    deleted = await repo.delete(entry.id, author_id="111", is_admin=False)
    assert deleted is False
    assert await repo.get_by_id(entry.id) is not None


async def test_delete_any_entry_succeeds_as_admin(repo):
    entry = await repo.save(content="admin can delete", tags=[], author_id="999", author_name="other")
    deleted = await repo.delete(entry.id, author_id="111", is_admin=True)
    assert deleted is True
    assert await repo.get_by_id(entry.id) is None
