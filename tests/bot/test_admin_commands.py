from unittest.mock import AsyncMock, MagicMock
from datetime import datetime, timezone
import discord
from lilwman.bot.commands.admin import AdminCog
from lilwman.domain.admin_entities import BotStats, GuildConfig
from lilwman.domain.entities import Entry


def _make_bot(**kwargs):
    bot = MagicMock()
    bot.get_stats = kwargs.get("get_stats", AsyncMock())
    bot.edit_entry = kwargs.get("edit_entry", AsyncMock())
    bot.list_by_author = kwargs.get("list_by_author", AsyncMock())
    bot.purge_by_author = kwargs.get("purge_by_author", AsyncMock())
    bot.purge_by_tag = kwargs.get("purge_by_tag", AsyncMock())
    bot.get_guild_config = kwargs.get("get_guild_config", AsyncMock())
    bot.set_guild_config = kwargs.get("set_guild_config", AsyncMock())
    bot.list_all_entries = kwargs.get("list_all_entries", AsyncMock())
    return bot


def _make_interaction(is_admin=True, guild_id=111):
    interaction = AsyncMock(spec=discord.Interaction)
    interaction.user = MagicMock()
    interaction.user.guild_permissions = MagicMock()
    interaction.user.guild_permissions.administrator = is_admin
    interaction.guild_id = guild_id
    interaction.response = AsyncMock()
    return interaction


def _make_entry(id=1):
    now = datetime.now(timezone.utc)
    return Entry(id=id, content="test", tags=["a"], author_id="u1",
                 author_name="Alice", created_at=now, updated_at=now)


async def test_admin_stats_returns_embed():
    now = datetime.now(timezone.utc)
    stats = BotStats(total_entries=5, entries_this_week=2, entries_this_month=4,
                     total_feeds=1, unique_tags=3, top_tags=[("py", 2)], top_authors=[("Alice", 5)])
    get_stats = AsyncMock()
    get_stats.execute = AsyncMock(return_value=stats)
    cog = AdminCog(_make_bot(get_stats=get_stats))
    interaction = _make_interaction()

    await cog.admin_stats.callback(cog, interaction)

    interaction.response.send_message.assert_called_once()
    call_kwargs = interaction.response.send_message.call_args
    assert call_kwargs.kwargs.get("ephemeral") is True


async def test_admin_non_admin_denied():
    cog = AdminCog(_make_bot())
    interaction = _make_interaction(is_admin=False)
    await cog.admin_stats.callback(cog, interaction)
    call_str = str(interaction.response.send_message.call_args).lower()
    assert "administrator" in call_str or "permission" in call_str


async def test_admin_dm_denied():
    cog = AdminCog(_make_bot())
    interaction = _make_interaction(guild_id=None)
    await cog.admin_stats.callback(cog, interaction)
    call_str = str(interaction.response.send_message.call_args).lower()
    assert "server" in call_str or "guild" in call_str


async def test_admin_edit_calls_use_case():
    edit_uc = AsyncMock()
    edit_uc.execute = AsyncMock(return_value=_make_entry())
    cog = AdminCog(_make_bot(edit_entry=edit_uc))
    interaction = _make_interaction()

    await cog.admin_edit.callback(cog, interaction, id=1, content="new content", tags="a, b")

    edit_uc.execute.assert_called_once_with(1, "new content", ["a", "b"])
    interaction.response.send_message.assert_called_once()


async def test_admin_purge_user_shows_confirmation():
    purge_uc = AsyncMock()
    purge_uc.execute = AsyncMock(return_value=3)
    list_uc = AsyncMock()
    list_uc.execute = AsyncMock(return_value=[_make_entry(), _make_entry(2), _make_entry(3)])
    cog = AdminCog(_make_bot(purge_by_author=purge_uc, list_by_author=list_uc))
    interaction = _make_interaction()
    user = MagicMock(spec=discord.Member)
    user.id = 999

    await cog.purge_user.callback(cog, interaction, user=user)

    interaction.response.send_message.assert_called_once()
    call_kwargs = interaction.response.send_message.call_args
    assert call_kwargs.kwargs.get("ephemeral") is True
    assert "view" in call_kwargs.kwargs


async def test_admin_config_show_returns_embed():
    now = datetime.now(timezone.utc)
    config = GuildConfig(guild_id="111", store_restricted=False, created_at=now, updated_at=now)
    get_cfg = AsyncMock()
    get_cfg.execute = AsyncMock(return_value=config)
    cog = AdminCog(_make_bot(get_guild_config=get_cfg))
    interaction = _make_interaction()

    await cog.config_show.callback(cog, interaction)

    interaction.response.send_message.assert_called_once()
    assert interaction.response.send_message.call_args.kwargs.get("ephemeral") is True


async def test_admin_purge_tag_shows_confirmation():
    purge_uc = MagicMock()
    purge_uc.execute = AsyncMock(return_value=3)

    cog = AdminCog(_make_bot(purge_by_tag=purge_uc))
    interaction = _make_interaction()

    await cog.purge_tag_cmd.callback(cog, interaction, tag="spam")

    interaction.response.send_message.assert_called_once()
    call_kwargs = interaction.response.send_message.call_args
    assert call_kwargs.kwargs.get("ephemeral") is True
    assert "view" in call_kwargs.kwargs


async def test_store_restricted_blocks_non_admin(monkeypatch):
    from lilwman.bot.commands.store import StoreCog
    now = datetime.now(timezone.utc)
    config = GuildConfig(guild_id="111", store_restricted=True, created_at=now, updated_at=now)
    get_cfg = AsyncMock()
    get_cfg.execute = AsyncMock(return_value=config)

    bot = MagicMock()
    bot.store_entry = AsyncMock()
    bot.get_guild_config = get_cfg
    cog = StoreCog(bot)

    interaction = AsyncMock(spec=discord.Interaction)
    interaction.user = MagicMock()
    interaction.user.guild_permissions = MagicMock()
    interaction.user.guild_permissions.administrator = False
    interaction.guild_id = 111
    interaction.response = AsyncMock()

    await cog.store.callback(cog, interaction, content="test", tags="")

    bot.store_entry.execute.assert_not_called()
    call_str = str(interaction.response.send_message.call_args).lower()
    assert "restricted" in call_str or "admin" in call_str
