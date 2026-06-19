import discord
from discord.ext import commands

from lilwman.application.store_entry import StoreEntryUseCase
from lilwman.application.search_entries import SearchEntriesUseCase
from lilwman.application.delete_entry import DeleteEntryUseCase
from lilwman.application.list_by_tag import ListByTagUseCase
from lilwman.application.ask_query import AskQueryUseCase


class LilwmanBot(commands.Bot):
    def __init__(
        self,
        guild_id: int,
        store_entry: StoreEntryUseCase,
        search_entries: SearchEntriesUseCase,
        delete_entry: DeleteEntryUseCase,
        list_by_tag: ListByTagUseCase,
        ask_query: AskQueryUseCase,
    ) -> None:
        intents = discord.Intents.default()
        super().__init__(command_prefix="!", intents=intents)
        self.guild_id = guild_id
        self.store_entry = store_entry
        self.search_entries = search_entries
        self.delete_entry = delete_entry
        self.list_by_tag = list_by_tag
        self.ask_query = ask_query

    async def setup_hook(self) -> None:
        from lilwman.bot.commands.store import StoreCog
        from lilwman.bot.commands.search import SearchCog
        from lilwman.bot.commands.delete import DeleteCog
        from lilwman.bot.commands.tag import TagCog
        from lilwman.bot.commands.ask import AskCog

        await self.add_cog(StoreCog(self))
        await self.add_cog(SearchCog(self))
        await self.add_cog(DeleteCog(self))
        await self.add_cog(TagCog(self))
        await self.add_cog(AskCog(self))

        guild = discord.Object(id=self.guild_id)
        self.tree.copy_global_to(guild=guild)
        await self.tree.sync(guild=guild)

    async def on_ready(self) -> None:
        print(f"Logged in as {self.user} (ID: {self.user.id})")
