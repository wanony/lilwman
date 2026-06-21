import discord
from discord import app_commands
from discord.ext import commands


class StoreCog(commands.Cog):
    def __init__(self, bot) -> None:
        self.bot = bot

    @app_commands.command(name="store", description="Store a wiki entry")
    @app_commands.describe(
        content="The content to store",
        tags="Comma-separated tags (optional)",
    )
    async def store(
        self,
        interaction: discord.Interaction,
        content: str,
        tags: str = "",
    ) -> None:
        guild_id = str(interaction.guild_id) if interaction.guild_id else ""
        is_admin = getattr(
            getattr(interaction.user, "guild_permissions", None), "administrator", False
        )
        if guild_id and not is_admin:
            config = await self.bot.get_guild_config.execute(guild_id)
            if config.store_restricted:
                await interaction.response.send_message(
                    "Storing entries is restricted to admins on this server.",
                    ephemeral=True,
                )
                return
        tag_list = [t.strip() for t in tags.split(",") if t.strip()]
        entry = await self.bot.store_entry.execute(
            content=content,
            tags=tag_list,
            author_id=str(interaction.user.id),
            author_name=interaction.user.display_name,
            guild_id=guild_id,
        )
        tag_display = f" [{', '.join(entry.tags)}]" if entry.tags else ""
        await interaction.response.send_message(
            f"Stored entry **#{entry.id}**{tag_display}."
        )
