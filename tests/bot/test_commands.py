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


def make_interaction(user_id="111", username="alice", is_admin=False, guild_id=None):
    interaction = AsyncMock(spec=discord.Interaction)
    interaction.user = MagicMock()
    interaction.user.id = user_id
    interaction.user.display_name = username
    interaction.user.guild_permissions = MagicMock()
    interaction.user.guild_permissions.administrator = is_admin
    interaction.guild_id = guild_id
    interaction.response = AsyncMock()
    interaction.followup = AsyncMock()
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
        guild_id="",
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

    await cog.search.callback(cog, interaction, query="zzznomatch")

    interaction.response.send_message.assert_called_once()
    call_str = str(interaction.response.send_message.call_args)
    assert "no results" in call_str.lower()


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
    call_str = str(interaction.response.send_message.call_args)
    assert "#5" in call_str
    assert "ephemeral=True" in call_str or "True" in call_str


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
    kwargs = interaction.response.send_message.call_args.kwargs
    assert "embed" in kwargs
    embed = kwargs["embed"]
    assert "nix" in embed.title.lower()


async def test_tag_no_entries_sends_message():
    list_uc = AsyncMock()
    list_uc.execute = AsyncMock(return_value=[])
    bot = make_bot(list_by_tag=list_uc)

    cog = TagCog(bot)
    interaction = make_interaction()

    await cog.tag.callback(cog, interaction, name="unknown")

    call_str = str(interaction.response.send_message.call_args)
    assert "no entries" in call_str.lower() or "nothing" in call_str.lower()


# --- /ask ---
from lilwman.bot.commands.ask import AskCog


async def test_ask_sends_llm_answer():
    ask_uc = AsyncMock()
    ask_uc.execute = AsyncMock(return_value="The answer is 42.")
    bot = make_bot(ask_query=ask_uc)

    cog = AskCog(bot)
    interaction = make_interaction()

    await cog.ask.callback(cog, interaction, question="What is the answer?")

    ask_uc.execute.assert_called_once_with("What is the answer?")
    interaction.response.defer.assert_called_once()
    interaction.followup.send.assert_called_once()
    call_str = str(interaction.followup.send.call_args)
    assert "42" in call_str


async def test_ask_sends_not_found_message():
    ask_uc = AsyncMock()
    ask_uc.execute = AsyncMock(return_value="Nothing in the wiki about that.")
    bot = make_bot(ask_query=ask_uc)

    cog = AskCog(bot)
    interaction = make_interaction()

    await cog.ask.callback(cog, interaction, question="unknown topic")

    interaction.response.defer.assert_called_once()
    call_str = str(interaction.followup.send.call_args)
    assert "nothing" in call_str.lower() or "wiki" in call_str.lower()


# --- SearchPaginator ---
from lilwman.bot.commands.search import SearchPaginator, PER_PAGE


def test_paginator_total_pages_single_page():
    results = [make_entry(id=i) for i in range(1, 4)]  # 3 entries < PER_PAGE(5)
    p = SearchPaginator(results, "q")
    assert p.total_pages == 1


def test_paginator_total_pages_exact_boundary():
    results = [make_entry(id=i) for i in range(1, PER_PAGE + 1)]  # exactly 5
    p = SearchPaginator(results, "q")
    assert p.total_pages == 1


def test_paginator_total_pages_over_boundary():
    results = [make_entry(id=i) for i in range(1, PER_PAGE + 2)]  # 6 entries
    p = SearchPaginator(results, "q")
    assert p.total_pages == 2


def test_paginator_embed_title_includes_query():
    results = [make_entry(id=1)]
    p = SearchPaginator(results, "my search")
    embed = p.make_embed()
    assert "my search" in embed.title


def test_paginator_embed_footer_shows_page_count():
    results = [make_entry(id=i) for i in range(1, 7)]  # 2 pages
    p = SearchPaginator(results, "q")
    embed = p.make_embed()
    assert "1/2" in embed.footer.text


async def test_paginator_prev_button_decrements_page():
    results = [make_entry(id=i) for i in range(1, 7)]  # 2 pages
    p = SearchPaginator(results, "q")
    p.page = 1

    interaction = AsyncMock()
    interaction.response = AsyncMock()

    await p.prev.callback(interaction)

    assert p.page == 0
    interaction.response.edit_message.assert_called_once()


async def test_paginator_prev_button_clamped_at_zero():
    results = [make_entry(id=i) for i in range(1, 4)]
    p = SearchPaginator(results, "q")
    p.page = 0

    interaction = AsyncMock()
    interaction.response = AsyncMock()

    await p.prev.callback(interaction)

    assert p.page == 0
    interaction.response.edit_message.assert_called_once()


async def test_paginator_next_button_increments_page():
    results = [make_entry(id=i) for i in range(1, 7)]  # 2 pages
    p = SearchPaginator(results, "q")
    p.page = 0

    interaction = AsyncMock()
    interaction.response = AsyncMock()

    await p.next.callback(interaction)

    assert p.page == 1
    interaction.response.edit_message.assert_called_once()


async def test_paginator_next_button_clamped_at_last_page():
    results = [make_entry(id=i) for i in range(1, 7)]  # 2 pages (0, 1)
    p = SearchPaginator(results, "q")
    p.page = 1  # already on last page

    interaction = AsyncMock()
    interaction.response = AsyncMock()

    await p.next.callback(interaction)

    assert p.page == 1
    interaction.response.edit_message.assert_called_once()


# --- TagCog overflow ---
async def test_tag_more_than_10_entries_shows_footer():
    entries = [make_entry(id=i) for i in range(1, 13)]  # 12 entries
    list_uc = AsyncMock()
    list_uc.execute = AsyncMock(return_value=entries)
    bot = make_bot(list_by_tag=list_uc)

    cog = TagCog(bot)
    interaction = make_interaction()

    await cog.tag.callback(cog, interaction, name="popular")

    kwargs = interaction.response.send_message.call_args.kwargs
    embed = kwargs["embed"]
    assert len(embed.fields) == 10
    assert "12" in embed.footer.text
