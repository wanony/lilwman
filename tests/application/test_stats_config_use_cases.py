import pytest
from lilwman.application.get_stats import GetStatsUseCase
from lilwman.application.get_guild_config import GetGuildConfigUseCase
from lilwman.application.set_guild_config import SetGuildConfigUseCase
from lilwman.application.store_entry import StoreEntryUseCase


async def test_get_stats_returns_bot_stats(repo, feed_repo):
    await repo.save("entry1", ["python"], "u1", "Alice", guild_id="g1")
    await repo.save("entry2", ["python", "discord"], "u2", "Bob", guild_id="g1")
    stats = await GetStatsUseCase(repo, feed_repo).execute("g1")
    assert stats.total_entries == 2
    assert stats.unique_tags == 2
    assert stats.total_feeds == 0


async def test_get_guild_config_returns_default(guild_config_repo):
    config = await GetGuildConfigUseCase(guild_config_repo).execute("new_guild")
    assert config.store_restricted is False
    assert config.guild_id == "new_guild"


async def test_set_guild_config_persists(guild_config_repo):
    await SetGuildConfigUseCase(guild_config_repo).execute("g1", store_restricted=True)
    config = await GetGuildConfigUseCase(guild_config_repo).execute("g1")
    assert config.store_restricted is True


async def test_store_entry_accepts_guild_id(repo):
    entry = await StoreEntryUseCase(repo).execute(
        content="test", tags=["a"], author_id="u1", author_name="Alice", guild_id="g1"
    )
    assert entry.guild_id == "g1"
