import discord
from discord import app_commands
from discord.ext import commands

from lilwman.application.add_feed import SUPPORTED_PLATFORMS


class FeedCog(commands.Cog):
    def __init__(self, bot) -> None:
        self.bot = bot

    feed = app_commands.Group(name="feed", description="Manage social media feed subscriptions")

    @feed.command(name="add", description="Subscribe this channel to a social media account")
    @app_commands.describe(
        platform=f"Platform ({', '.join(sorted(SUPPORTED_PLATFORMS))})",
        account="Account name, username, or subreddit",
    )
    async def feed_add(
        self, interaction: discord.Interaction, platform: str, account: str
    ) -> None:
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message(
                "Administrator permission required.", ephemeral=True
            )
            return
        platform = platform.lower().strip()
        if platform not in SUPPORTED_PLATFORMS:
            await interaction.response.send_message(
                f"Unknown platform **{platform}**. "
                f"Supported: {', '.join(sorted(SUPPORTED_PLATFORMS))}. "
                "For a custom RSS URL use `/feed addurl`.",
                ephemeral=True,
            )
            return
        channel_id = str(interaction.channel_id)
        sub = await self.bot.add_feed.execute(channel_id, platform, account)
        if sub is None:
            await interaction.response.send_message(
                f"Already subscribed to **{account}** on **{platform}** in this channel.",
                ephemeral=True,
            )
            return
        await interaction.response.send_message(
            f"Subscribed to **@{account}** on **{platform}** (id `{sub.id}`).",
            ephemeral=True,
        )

    @feed.command(name="addurl", description="Subscribe this channel to a custom RSS/Atom URL")
    @app_commands.describe(url="Full RSS or Atom feed URL")
    async def feed_addurl(self, interaction: discord.Interaction, url: str) -> None:
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message(
                "Administrator permission required.", ephemeral=True
            )
            return
        channel_id = str(interaction.channel_id)
        sub = await self.bot.add_feed.execute_custom_url(channel_id, url)
        if sub is None:
            await interaction.response.send_message(
                "Already subscribed to that URL in this channel.", ephemeral=True
            )
            return
        await interaction.response.send_message(
            f"Subscribed to custom feed (id `{sub.id}`).", ephemeral=True
        )

    @feed.command(name="remove", description="Remove a feed subscription from this channel")
    @app_commands.describe(id="Feed subscription id (from /feed list)")
    async def feed_remove(self, interaction: discord.Interaction, id: int) -> None:
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message(
                "Administrator permission required.", ephemeral=True
            )
            return
        channel_id = str(interaction.channel_id)
        deleted = await self.bot.remove_feed.execute(id, channel_id)
        if deleted:
            await interaction.response.send_message(f"Removed feed **#{id}**.", ephemeral=True)
        else:
            await interaction.response.send_message(
                f"Feed **#{id}** not found in this channel.", ephemeral=True
            )

    @feed.command(name="list", description="List feed subscriptions for this channel")
    async def feed_list(self, interaction: discord.Interaction) -> None:
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message(
                "Administrator permission required.", ephemeral=True
            )
            return
        channel_id = str(interaction.channel_id)
        subs = await self.bot.list_feeds.execute(channel_id)
        if not subs:
            await interaction.response.send_message(
                "No feeds subscribed in this channel.", ephemeral=True
            )
            return
        embed = discord.Embed(title="Feed Subscriptions", color=0x5865F2)
        for sub in subs:
            embed.add_field(
                name=f"#{sub.id} — {sub.platform}",
                value=f"@{sub.account_name}",
                inline=False,
            )
        await interaction.response.send_message(embed=embed, ephemeral=True)
