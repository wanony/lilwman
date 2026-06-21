import pytest
from lilwman.application.get_entry import GetEntryUseCase
from lilwman.application.edit_entry import EditEntryUseCase
from lilwman.application.list_by_author import ListByAuthorUseCase
from lilwman.application.list_all_entries import ListAllEntriesUseCase
from lilwman.application.purge_by_author import PurgeByAuthorUseCase
from lilwman.application.purge_by_tag import PurgeByTagUseCase


async def test_get_entry_returns_entry(repo):
    entry = await repo.save("hello", ["tag1"], "u1", "Alice")
    result = await GetEntryUseCase(repo).execute(entry.id)
    assert result is not None
    assert result.content == "hello"


async def test_get_entry_missing_returns_none(repo):
    result = await GetEntryUseCase(repo).execute(9999)
    assert result is None


async def test_edit_entry_updates_content_and_tags(repo):
    entry = await repo.save("original", ["old"], "u1", "Alice")
    result = await EditEntryUseCase(repo).execute(entry.id, "new content", ["new", "tag"])
    assert result is not None
    assert result.content == "new content"
    assert set(result.tags) == {"new", "tag"}


async def test_edit_entry_missing_returns_none(repo):
    result = await EditEntryUseCase(repo).execute(9999, "x", [])
    assert result is None


async def test_list_by_author_filters_correctly(repo):
    await repo.save("e1", [], "user1", "Alice")
    await repo.save("e2", [], "user2", "Bob")
    results = await ListByAuthorUseCase(repo).execute("user1")
    assert len(results) == 1
    assert results[0].author_id == "user1"


async def test_list_all_entries_pagination(repo):
    for i in range(5):
        await repo.save(f"entry {i}", [], "u1", "Alice")
    entries, total = await ListAllEntriesUseCase(repo).execute(page=1, per_page=3)
    assert total == 5
    assert len(entries) == 3
    entries_p2, _ = await ListAllEntriesUseCase(repo).execute(page=2, per_page=3)
    assert len(entries_p2) == 2


async def test_purge_by_author_returns_count(repo):
    await repo.save("e1", [], "u1", "Alice")
    await repo.save("e2", [], "u1", "Alice")
    await repo.save("e3", [], "u2", "Bob")
    count = await PurgeByAuthorUseCase(repo).execute("u1")
    assert count == 2
    _, total = await ListAllEntriesUseCase(repo).execute()
    assert total == 1


async def test_purge_by_tag_returns_count(repo):
    await repo.save("e1", ["spam"], "u1", "Alice")
    await repo.save("e2", ["spam", "ok"], "u2", "Bob")
    await repo.save("e3", ["ok"], "u3", "Carol")
    count = await PurgeByTagUseCase(repo).execute("spam")
    assert count == 2
    _, total = await ListAllEntriesUseCase(repo).execute()
    assert total == 1
