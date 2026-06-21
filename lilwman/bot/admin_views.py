from typing import Callable, Awaitable

import discord


class ConfirmView(discord.ui.View):
    def __init__(self, callback: Callable[[], Awaitable[int]], timeout: float = 60.0) -> None:
        super().__init__(timeout=timeout)
        self._callback = callback

    @discord.ui.button(label="Confirm", style=discord.ButtonStyle.danger)
    async def confirm(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        count = await self._callback()
        button.disabled = True
        self.stop()
        await interaction.response.edit_message(
            content=f"Done. Deleted **{count}** entries.", view=self
        )

    async def on_timeout(self) -> None:
        self.confirm.disabled = True
        self.stop()
