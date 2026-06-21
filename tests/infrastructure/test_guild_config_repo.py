from lilwman.infrastructure.db.guild_config_repo import SQLAlchemyGuildConfigRepository


async def test_get_returns_default_when_not_found(guild_config_repo):
    config = await guild_config_repo.get("unknown_guild")
    assert config.guild_id == "unknown_guild"
    assert config.store_restricted is False


async def test_save_and_get_roundtrip(guild_config_repo):
    await guild_config_repo.save("guild1", store_restricted=True)
    config = await guild_config_repo.get("guild1")
    assert config.store_restricted is True


async def test_save_overwrites_existing(guild_config_repo):
    await guild_config_repo.save("guild1", store_restricted=True)
    await guild_config_repo.save("guild1", store_restricted=False)
    config = await guild_config_repo.get("guild1")
    assert config.store_restricted is False
