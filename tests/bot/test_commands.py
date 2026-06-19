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


# --- /search ---
from lilwman.bot.commands.search import SearchCog


async def test_search_sends_embed_with_results():
    entries = [
        make_entry(id=i, content=f"result {i}", tags=["t"]) for i in range(1, 4)
    ]
    search_uc = AsyncMock()
    search_uc.execute = AsyncMock(return_value=entries)
    bot = make_bot(search_entries=search_uc)

    cog = SearchCog(bot)
    interaction = make_interaction()

    await cog.search.callback(cog, interaction, query="test")

    interaction.response.send_message.assert_called_once()
    kwargs = interaction.response.send_message.call_args.kwargs
    assert "embed" in kwargs or len(interaction.response.send_message.call_args.args) > 0


async def test_search_no_results_sends_message():
    search_uc = AsyncMock()
    search_uc.execute = AsyncMock(return_value=[])
    bot = make_bot(search_entries=search_uc)

    cog = SearchCog(bot)
    interaction = make_interaction()

    await cog.search.callback(cog, interaction, query="nothing")

    interaction.response.send_message.assert_called_once()
    call_str = str(interaction.response.send_message.call_args)
    assert "no results" in call_str.lower() or "nothing" in call_str.lower()


# --- /delete ---
from lilwman.bot.commands.delete import DeleteCog


async def test_delete_own_entry_sends_success():
    delete_uc = AsyncMock()
    delete_uc.execute = AsyncMock(return_value=True)
    bot = make_bot(delete_entry=delete_uc)

    cog = DeleteCog(bot)
    interaction = make_interaction(user_id="111")

    await cog.delete.callback(cog, interaction, id=5)

    delete_uc.execute.assert_called_once_with(
        entry_id=5, author_id="111", is_admin=False
    )
    interaction.response.send_message.assert_called_once()


async def test_delete_denied_sends_error():
    delete_uc = AsyncMock()
    delete_uc.execute = AsyncMock(return_value=False)
    bot = make_bot(delete_entry=delete_uc)

    cog = DeleteCog(bot)
    interaction = make_interaction(user_id="111")

    await cog.delete.callback(cog, interaction, id=99)

    call_str = str(interaction.response.send_message.call_args)
    assert "not found" in call_str.lower() or "permission" in call_str.lower() or "denied" in call_str.lower()


# --- /tag ---
from lilwman.bot.commands.tag import TagCog


async def test_tag_sends_embed_with_entries():
    entries = [make_entry(id=1, content="tagged entry", tags=["nix"])]
    list_uc = AsyncMock()
    list_uc.execute = AsyncMock(return_value=entries)
    bot = make_bot(list_by_tag=list_uc)

    cog = TagCog(bot)
    interaction = make_interaction()

    await cog.tag.callback(cog, interaction, name="nix")

    list_uc.execute.assert_called_once_with("nix")
    interaction.response.send_message.assert_called_once()


async def test_tag_no_entries_sends_message():
    list_uc = AsyncMock()
    list_uc.execute = AsyncMock(return_value=[])
    bot = make_bot(list_by_tag=list_uc)

    cog = TagCog(bot)
    interaction = make_interaction()

    await cog.tag.callback(cog, interaction, name="unknown")

    call_str = str(interaction.response.send_message.call_args)
    assert "no entries" in call_str.lower() or "nothing" in call_str.lower()
