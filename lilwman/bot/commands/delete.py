import discord
from discord import app_commands
from discord.ext import commands


class DeleteCog(commands.Cog):
    def __init__(self, bot) -> None:
        self.bot = bot

    @app_commands.command(name="delete", description="Delete a wiki entry")
    @app_commands.describe(id="ID of the entry to delete")
    async def delete(self, interaction: discord.Interaction, id: int) -> None:
        is_admin = interaction.user.guild_permissions.administrator
        deleted = await self.bot.delete_entry.execute(
            entry_id=id,
            author_id=str(interaction.user.id),
            is_admin=is_admin,
        )
        if deleted:
            await interaction.response.send_message(
                f"Deleted entry **#{id}**.", ephemeral=True
            )
        else:
            await interaction.response.send_message(
                f"Entry **#{id}** not found or permission denied.", ephemeral=True
            )
