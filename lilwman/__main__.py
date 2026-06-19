import asyncio
import os

from lilwman.config import Settings
from lilwman.infrastructure.db.session import create_engine, create_session_factory, init_db
from lilwman.infrastructure.db.repository import SQLAlchemyEntryRepository
from lilwman.infrastructure.llm.ollama import OllamaLLM
from lilwman.application.store_entry import StoreEntryUseCase
from lilwman.application.search_entries import SearchEntriesUseCase
from lilwman.application.delete_entry import DeleteEntryUseCase
from lilwman.application.list_by_tag import ListByTagUseCase
from lilwman.application.ask_query import AskQueryUseCase
from lilwman.bot.bot import LilwmanBot


async def main() -> None:
    settings = Settings()

    db_dir = os.path.dirname(settings.db_path)
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)

    engine = create_engine(settings.db_path)
    await init_db(engine)
    session_factory = create_session_factory(engine)

    repo = SQLAlchemyEntryRepository(session_factory)
    llm = OllamaLLM(host=settings.ollama_host, model=settings.ollama_model)

    store_entry = StoreEntryUseCase(repo)
    search_entries = SearchEntriesUseCase(repo)
    delete_entry = DeleteEntryUseCase(repo)
    list_by_tag = ListByTagUseCase(repo)
    ask_query = AskQueryUseCase(repo, llm)

    bot = LilwmanBot(
        guild_id=settings.discord_guild_id,
        store_entry=store_entry,
        search_entries=search_entries,
        delete_entry=delete_entry,
        list_by_tag=list_by_tag,
        ask_query=ask_query,
    )

    await bot.start(settings.discord_token)


if __name__ == "__main__":
    asyncio.run(main())
