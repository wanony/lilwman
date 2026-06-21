# lilwman/bot/bot.py
import discord
from discord import app_commands
from discord.ext import commands

from lilwman.application.store_entry import StoreEntryUseCase
from lilwman.application.search_entries import SearchEntriesUseCase
from lilwman.application.delete_entry import DeleteEntryUseCase
from lilwman.application.list_by_tag import ListByTagUseCase
from lilwman.application.ask_query import AskQueryUseCase
from lilwman.application.add_feed import AddFeedUseCase
from lilwman.application.remove_feed import RemoveFeedUseCase
from lilwman.application.list_feeds import ListFeedsUseCase
from lilwman.application.poll_feeds import PollFeedsUseCase


class LilwmanBot(commands.Bot):
    def __init__(
        self,
        guild_id: int,
        store_entry: StoreEntryUseCase,
        search_entries: SearchEntriesUseCase,
        delete_entry: DeleteEntryUseCase,
        list_by_tag: ListByTagUseCase,
        ask_query: AskQueryUseCase,
        add_feed: AddFeedUseCase,
        remove_feed: RemoveFeedUseCase,
        list_feeds: ListFeedsUseCase,
        poll_feeds: PollFeedsUseCase,
    ) -> None:
        intents = discord.Intents.default()
        super().__init__(command_prefix="!", intents=intents)
        self.guild_id = guild_id
        self.store_entry = store_entry
        self.search_entries = search_entries
        self.delete_entry = delete_entry
        self.list_by_tag = list_by_tag
        self.ask_query = ask_query
        self.add_feed = add_feed
        self.remove_feed = remove_feed
        self.list_feeds = list_feeds
        self.poll_feeds = poll_feeds

    async def setup_hook(self) -> None:
        from lilwman.bot.commands.store import StoreCog
        from lilwman.bot.commands.search import SearchCog
        from lilwman.bot.commands.delete import DeleteCog
        from lilwman.bot.commands.tag import TagCog
        from lilwman.bot.commands.ask import AskCog
        from lilwman.bot.commands.feed import FeedCog
        from lilwman.bot.poller import FeedPoller

        await self.add_cog(StoreCog(self))
        await self.add_cog(SearchCog(self))
        await self.add_cog(DeleteCog(self))
        await self.add_cog(TagCog(self))
        await self.add_cog(AskCog(self))
        await self.add_cog(FeedCog(self))
        await self.add_cog(FeedPoller(self, self.poll_feeds))

        guild = discord.Object(id=self.guild_id)
        self.tree.copy_global_to(guild=guild)
        await self.tree.sync(guild=guild)

    async def on_app_command_error(
        self,
        interaction: discord.Interaction,
        error: app_commands.AppCommandError,
    ) -> None:
        msg = "Something went wrong. Please try again."
        if interaction.response.is_done():
            await interaction.followup.send(msg, ephemeral=True)
        else:
            await interaction.response.send_message(msg, ephemeral=True)

    async def on_ready(self) -> None:
        print(f"Logged in as {self.user} (ID: {self.user.id})")
