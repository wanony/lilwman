import discord

from lilwman.bot.feed_utils import get_platform_colour
from lilwman.domain.feed_entities import FeedPost, FeedSubscription


class FeedImagePaginator(discord.ui.View):
    def __init__(self, post: FeedPost, subscription: FeedSubscription) -> None:
        super().__init__(timeout=120)
        self.post = post
        self.subscription = subscription
        self.page = 0

    @property
    def total_pages(self) -> int:
        return len(self.post.images)

    def make_embed(self, colour: int) -> discord.Embed:
        embed = discord.Embed(
            title=self.post.title,
            url=self.post.url,
            description=self.post.description,
            color=colour,
        )
        embed.set_author(
            name=f"@{self.subscription.account_name} on {self.subscription.platform}"
        )
        embed.set_image(url=self.post.images[self.page])
        embed.set_footer(text=f"Image {self.page + 1}/{self.total_pages}")
        embed.timestamp = self.post.published_at
        return embed

    @discord.ui.button(label="◀", style=discord.ButtonStyle.secondary)
    async def prev(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        self.page = max(0, self.page - 1)
        await interaction.response.edit_message(
            embed=self.make_embed(get_platform_colour(self.subscription.platform)), view=self
        )

    @discord.ui.button(label="▶", style=discord.ButtonStyle.secondary)
    async def next(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        self.page = min(self.total_pages - 1, self.page + 1)
        await interaction.response.edit_message(
            embed=self.make_embed(get_platform_colour(self.subscription.platform)), view=self
        )
