import discord
from discord import app_commands
from discord.ext import commands

from lilwman.domain.entities import Entry

PER_PAGE = 5


class SearchPaginator(discord.ui.View):
    def __init__(self, results: list[Entry], query: str) -> None:
        super().__init__(timeout=60)
        self.results = results
        self.query = query
        self.page = 0

    @property
    def total_pages(self) -> int:
        return max(1, (len(self.results) + PER_PAGE - 1) // PER_PAGE)

    def make_embed(self) -> discord.Embed:
        start = self.page * PER_PAGE
        page_entries = self.results[start : start + PER_PAGE]
        embed = discord.Embed(
            title=f"Search: {self.query}",
            color=0x5865F2,
        )
        for entry in page_entries:
            tags = ", ".join(entry.tags) if entry.tags else "no tags"
            embed.add_field(
                name=f"#{entry.id} — {entry.author_name} [{tags}]",
                value=entry.content[:200] or "​",
                inline=False,
            )
        embed.set_footer(text=f"Page {self.page + 1}/{self.total_pages}")
        return embed

    @discord.ui.button(label="◀", style=discord.ButtonStyle.secondary)
    async def prev(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        self.page = max(0, self.page - 1)
        await interaction.response.edit_message(embed=self.make_embed(), view=self)

    @discord.ui.button(label="▶", style=discord.ButtonStyle.secondary)
    async def next(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        self.page = min(self.total_pages - 1, self.page + 1)
        await interaction.response.edit_message(embed=self.make_embed(), view=self)


class SearchCog(commands.Cog):
    def __init__(self, bot) -> None:
        self.bot = bot

    @app_commands.command(name="search", description="Search the wiki")
    @app_commands.describe(query="Keywords to search for")
    async def search(self, interaction: discord.Interaction, query: str) -> None:
        results = await self.bot.search_entries.execute(query)
        if not results:
            await interaction.response.send_message(
                f"No results for **{query}**.", ephemeral=True
            )
            return
        paginator = SearchPaginator(results, query)
        await interaction.response.send_message(
            embed=paginator.make_embed(), view=paginator
        )
