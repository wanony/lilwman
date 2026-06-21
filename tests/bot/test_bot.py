from unittest.mock import AsyncMock, MagicMock
import discord
from discord import app_commands

from lilwman.bot.bot import LilwmanBot


def make_bot_instance():
    return LilwmanBot(
        guild_id=1,
        store_entry=AsyncMock(),
        search_entries=AsyncMock(),
        delete_entry=AsyncMock(),
        list_by_tag=AsyncMock(),
        ask_query=AsyncMock(),
        add_feed=MagicMock(),
        remove_feed=MagicMock(),
        list_feeds=MagicMock(),
        poll_feeds=MagicMock(),
        get_stats=MagicMock(),
        get_entry=MagicMock(),
        edit_entry=MagicMock(),
        list_all_entries=MagicMock(),
        list_by_author=MagicMock(),
        purge_by_author=MagicMock(),
        purge_by_tag=MagicMock(),
        get_guild_config=MagicMock(),
        set_guild_config=MagicMock(),
    )


async def test_error_handler_sends_message_when_response_not_done():
    bot = make_bot_instance()

    interaction = AsyncMock(spec=discord.Interaction)
    interaction.response = AsyncMock()
    interaction.response.is_done = MagicMock(return_value=False)
    interaction.followup = AsyncMock()

    error = app_commands.AppCommandError("test error")
    await bot.on_app_command_error(interaction, error)

    interaction.response.send_message.assert_called_once()
    kwargs = interaction.response.send_message.call_args.kwargs
    assert kwargs.get("ephemeral") is True


async def test_error_handler_uses_followup_when_response_done():
    bot = make_bot_instance()

    interaction = AsyncMock(spec=discord.Interaction)
    interaction.response = AsyncMock()
    interaction.response.is_done = MagicMock(return_value=True)
    interaction.followup = AsyncMock()

    error = app_commands.AppCommandError("test error")
    await bot.on_app_command_error(interaction, error)

    interaction.followup.send.assert_called_once()
    kwargs = interaction.followup.send.call_args.kwargs
    assert kwargs.get("ephemeral") is True


async def test_error_handler_message_text():
    bot = make_bot_instance()

    interaction = AsyncMock(spec=discord.Interaction)
    interaction.response = AsyncMock()
    interaction.response.is_done = MagicMock(return_value=False)
    interaction.followup = AsyncMock()

    error = app_commands.AppCommandError("oops")
    await bot.on_app_command_error(interaction, error)

    call_args = interaction.response.send_message.call_args
    message = call_args.args[0] if call_args.args else call_args.kwargs.get("content", "")
    assert "wrong" in message.lower() or "try again" in message.lower()
