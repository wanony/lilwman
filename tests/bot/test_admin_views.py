from unittest.mock import AsyncMock, MagicMock
import discord
from lilwman.bot.admin_views import ConfirmView


async def test_confirm_button_calls_callback():
    callback = AsyncMock(return_value=5)
    view = ConfirmView(callback)

    interaction = AsyncMock(spec=discord.Interaction)
    interaction.response = AsyncMock()

    await view.confirm.callback(interaction)

    callback.assert_called_once()
    interaction.response.edit_message.assert_called_once()
    # Verify button is disabled after confirm
    assert view.confirm.disabled is True


async def test_on_timeout_disables_button():
    view = ConfirmView(AsyncMock())
    await view.on_timeout()
    assert view.confirm.disabled is True
