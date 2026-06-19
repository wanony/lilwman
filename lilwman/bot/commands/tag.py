import discord
from discord import app_commands
from discord.ext import commands


class TagCog(commands.Cog):
    def __init__(self, bot) -> None:
        self.bot = bot

    @app_commands.command(name="tag", description="List entries with a tag")
    @app_commands.describe(name="Tag name to list")
    async def tag(self, interaction: discord.Interaction, name: str) -> None:
        entries = await self.bot.list_by_tag.execute(name)
        if not entries:
            await interaction.response.send_message(
                f"No entries tagged **{name}**.", ephemeral=True
            )
            return
        embed = discord.Embed(title=f"Tag: {name}", color=0x57F287)
        for entry in entries[:10]:
            embed.add_field(
                name=f"#{entry.id} — {entry.author_name}",
                value=entry.content[:200] or "​",
                inline=False,
            )
        if len(entries) > 10:
            embed.set_footer(text=f"Showing 10 of {len(entries)} entries")
        await interaction.response.send_message(embed=embed)
