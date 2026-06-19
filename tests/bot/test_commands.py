from unittest.mock import AsyncMock, MagicMock
from datetime import datetime, timezone
import pytest
import discord

from lilwman.domain.entities import Entry
from lilwman.bot.commands.store import StoreCog


def make_bot(store_entry=None, search_entries=None, delete_entry=None,
             list_by_tag=None, ask_query=None):
    bot = MagicMock()
    bot.store_entry = store_entry or AsyncMock()
    bot.search_entries = search_entries or AsyncMock()
    bot.delete_entry = delete_entry or AsyncMock()
    bot.list_by_tag = list_by_tag or AsyncMock()
    bot.ask_query = ask_query or AsyncMock()
    return bot


def make_interaction(user_id="111", username="alice", is_admin=False):
    interaction = AsyncMock(spec=discord.Interaction)
    interaction.user = MagicMock()
    interaction.user.id = user_id
    interaction.user.display_name = username
    interaction.user.guild_permissions = MagicMock()
    interaction.user.guild_permissions.administrator = is_admin
    interaction.response = AsyncMock()
    return interaction


def make_entry(**kwargs):
    defaults = dict(
        id=1,
        content="test content",
        tags=[],
        author_id="111",
        author_name="alice",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    return Entry(**{**defaults, **kwargs})


async def test_store_command_replies_with_entry_id():
    entry = make_entry(id=42, content="hello world", tags=["greet"])
    store_uc = AsyncMock()
    store_uc.execute = AsyncMock(return_value=entry)
    bot = make_bot(store_entry=store_uc)

    cog = StoreCog(bot)
    interaction = make_interaction()

    await cog.store.callback(cog, interaction, content="hello world", tags="greet")

    interaction.response.send_message.assert_called_once()
    call_args = interaction.response.send_message.call_args
    assert "42" in str(call_args)


async def test_store_command_passes_tags_to_use_case():
    entry = make_entry(id=1, tags=["a", "b"])
    store_uc = AsyncMock()
    store_uc.execute = AsyncMock(return_value=entry)
    bot = make_bot(store_entry=store_uc)

    cog = StoreCog(bot)
    interaction = make_interaction()

    await cog.store.callback(cog, interaction, content="content", tags="a, b")

    store_uc.execute.assert_called_once_with(
        content="content",
        tags=["a", "b"],
        author_id="111",
        author_name="alice",
    )
