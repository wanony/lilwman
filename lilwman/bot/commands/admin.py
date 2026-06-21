import discord
from discord import app_commands
from discord.ext import commands

from lilwman.bot.admin_views import ConfirmView


def _is_admin(interaction: discord.Interaction) -> bool:
    return getattr(
        getattr(interaction.user, "guild_permissions", None), "administrator", False
    )


class AdminCog(commands.Cog):
    def __init__(self, bot) -> None:
        self.bot = bot

    admin = app_commands.Group(name="admin", description="Admin tools")
    purge = app_commands.Group(name="purge", description="Purge entries", parent=admin)
    admin_config = app_commands.Group(name="config", description="Guild config", parent=admin)

    @admin.command(name="stats", description="Show bot interaction stats for this server")
    async def admin_stats(self, interaction: discord.Interaction) -> None:
        if interaction.guild_id is None:
            await interaction.response.send_message(
                "Admin commands can only be used in a server.", ephemeral=True
            )
            return
        if not _is_admin(interaction):
            await interaction.response.send_message(
                "Administrator permission required.", ephemeral=True
            )
            return
        stats = await self.bot.get_stats.execute(str(interaction.guild_id))
        embed = discord.Embed(title="Bot Stats", color=0x5865F2)
        embed.add_field(name="Total entries", value=str(stats.total_entries), inline=True)
        embed.add_field(name="This week", value=str(stats.entries_this_week), inline=True)
        embed.add_field(name="This month", value=str(stats.entries_this_month), inline=True)
        embed.add_field(name="Feed subscriptions", value=str(stats.total_feeds), inline=True)
        embed.add_field(name="Unique tags", value=str(stats.unique_tags), inline=True)
        if stats.top_tags:
            embed.add_field(
                name="Top tags",
                value="\n".join(f"{t}: {c}" for t, c in stats.top_tags[:5]),
                inline=False,
            )
        if stats.top_authors:
            embed.add_field(
                name="Top authors",
                value="\n".join(f"{a}: {c}" for a, c in stats.top_authors[:5]),
                inline=False,
            )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @admin.command(name="list-user", description="List entries by a user")
    @app_commands.describe(user="Discord member")
    async def admin_list_user(self, interaction: discord.Interaction, user: discord.Member) -> None:
        if interaction.guild_id is None:
            await interaction.response.send_message(
                "Admin commands can only be used in a server.", ephemeral=True
            )
            return
        if not _is_admin(interaction):
            await interaction.response.send_message(
                "Administrator permission required.", ephemeral=True
            )
            return
        entries = await self.bot.list_by_author.execute(str(user.id))
        if not entries:
            await interaction.response.send_message(
                f"No entries for **{user.display_name}**.", ephemeral=True
            )
            return
        embed = discord.Embed(
            title=f"Entries by {user.display_name}",
            description=f"{len(entries)} total",
            color=0x5865F2,
        )
        for entry in entries[:10]:
            tags = ", ".join(entry.tags) if entry.tags else "no tags"
            embed.add_field(
                name=f"#{entry.id} [{tags}]",
                value=entry.content[:200] or "​",
                inline=False,
            )
        if len(entries) > 10:
            embed.set_footer(text=f"Showing 10 of {len(entries)}")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @admin.command(name="edit", description="Edit any entry")
    @app_commands.describe(id="Entry ID", content="New content", tags="Comma-separated tags")
    async def admin_edit(
        self,
        interaction: discord.Interaction,
        id: int,
        content: str,
        tags: str = "",
    ) -> None:
        if interaction.guild_id is None:
            await interaction.response.send_message(
                "Admin commands can only be used in a server.", ephemeral=True
            )
            return
        if not _is_admin(interaction):
            await interaction.response.send_message(
                "Administrator permission required.", ephemeral=True
            )
            return
        tag_list = [t.strip() for t in tags.split(",") if t.strip()]
        entry = await self.bot.edit_entry.execute(id, content, tag_list)
        if entry is None:
            await interaction.response.send_message(
                f"Entry **#{id}** not found.", ephemeral=True
            )
            return
        await interaction.response.send_message(
            f"Updated entry **#{entry.id}**.", ephemeral=True
        )

    @purge.command(name="user", description="Delete all entries by a user")
    @app_commands.describe(user="Discord member whose entries to delete")
    async def purge_user(self, interaction: discord.Interaction, user: discord.Member) -> None:
        if interaction.guild_id is None:
            await interaction.response.send_message(
                "Admin commands can only be used in a server.", ephemeral=True
            )
            return
        if not _is_admin(interaction):
            await interaction.response.send_message(
                "Administrator permission required.", ephemeral=True
            )
            return
        entries = await self.bot.list_by_author.execute(str(user.id))
        count = len(entries)
        if count == 0:
            await interaction.response.send_message(
                f"No entries found for **{user.display_name}**.", ephemeral=True
            )
            return

        async def do_purge() -> int:
            return await self.bot.purge_by_author.execute(str(user.id))

        view = ConfirmView(do_purge)
        await interaction.response.send_message(
            f"This will delete **{count}** entries by **{user.display_name}**. Confirm?",
            ephemeral=True,
            view=view,
        )

    @purge.command(name="tag", description="Delete all entries with a tag")
    @app_commands.describe(tag="Tag name to purge")
    async def purge_tag_cmd(self, interaction: discord.Interaction, tag: str) -> None:
        if interaction.guild_id is None:
            await interaction.response.send_message(
                "Admin commands can only be used in a server.", ephemeral=True
            )
            return
        if not _is_admin(interaction):
            await interaction.response.send_message(
                "Administrator permission required.", ephemeral=True
            )
            return

        async def do_purge() -> int:
            return await self.bot.purge_by_tag.execute(tag)

        view = ConfirmView(do_purge)
        await interaction.response.send_message(
            f"This will delete all entries tagged **{tag}**. Confirm?",
            ephemeral=True,
            view=view,
        )

    @admin_config.command(name="show", description="Show current guild configuration")
    async def config_show(self, interaction: discord.Interaction) -> None:
        if interaction.guild_id is None:
            await interaction.response.send_message(
                "Admin commands can only be used in a server.", ephemeral=True
            )
            return
        if not _is_admin(interaction):
            await interaction.response.send_message(
                "Administrator permission required.", ephemeral=True
            )
            return
        config = await self.bot.get_guild_config.execute(str(interaction.guild_id))
        embed = discord.Embed(title="Guild Configuration", color=0x5865F2)
        embed.add_field(
            name="store_restricted",
            value=(
                "✅ Enabled (only admins can /store)"
                if config.store_restricted
                else "❌ Disabled (anyone can /store)"
            ),
            inline=False,
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @admin_config.command(name="set", description="Update guild configuration")
    @app_commands.describe(store_restricted="Restrict /store to administrators only")
    async def config_set(
        self, interaction: discord.Interaction, store_restricted: bool
    ) -> None:
        if interaction.guild_id is None:
            await interaction.response.send_message(
                "Admin commands can only be used in a server.", ephemeral=True
            )
            return
        if not _is_admin(interaction):
            await interaction.response.send_message(
                "Administrator permission required.", ephemeral=True
            )
            return
        await self.bot.set_guild_config.execute(str(interaction.guild_id), store_restricted)
        state = "enabled" if store_restricted else "disabled"
        await interaction.response.send_message(
            f"store_restricted {state}.", ephemeral=True
        )
