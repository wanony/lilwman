# lilwman/__main__.py
import asyncio
import os

import uvicorn

from lilwman.config import Settings
from lilwman.infrastructure.db.session import create_engine, create_session_factory, init_db
from lilwman.infrastructure.db.repository import SQLAlchemyEntryRepository
from lilwman.infrastructure.db.feed_repository import SQLAlchemyFeedRepository
from lilwman.infrastructure.db.guild_config_repo import SQLAlchemyGuildConfigRepository
from lilwman.infrastructure.http.feed_fetcher import AiohttpFeedFetcher
from lilwman.infrastructure.llm.ollama import OllamaLLM
from lilwman.application.store_entry import StoreEntryUseCase
from lilwman.application.search_entries import SearchEntriesUseCase
from lilwman.application.delete_entry import DeleteEntryUseCase
from lilwman.application.list_by_tag import ListByTagUseCase
from lilwman.application.ask_query import AskQueryUseCase
from lilwman.application.add_feed import AddFeedUseCase
from lilwman.application.remove_feed import RemoveFeedUseCase
from lilwman.application.list_feeds import ListFeedsUseCase
from lilwman.application.poll_feeds import PollFeedsUseCase
from lilwman.application.get_stats import GetStatsUseCase
from lilwman.application.get_entry import GetEntryUseCase
from lilwman.application.edit_entry import EditEntryUseCase
from lilwman.application.list_all_entries import ListAllEntriesUseCase
from lilwman.application.list_by_author import ListByAuthorUseCase
from lilwman.application.purge_by_author import PurgeByAuthorUseCase
from lilwman.application.purge_by_tag import PurgeByTagUseCase
from lilwman.application.get_guild_config import GetGuildConfigUseCase
from lilwman.application.set_guild_config import SetGuildConfigUseCase
from lilwman.infrastructure.web.app import create_app
from lilwman.bot.bot import LilwmanBot


async def main() -> None:
    settings = Settings()

    if settings.web_secret_key == "":
        raise RuntimeError(
            "WEB_SECRET_KEY must be set. "
            "Generate one with: python -c \"import secrets; print(secrets.token_hex(32))\""
        )

    db_dir = os.path.dirname(settings.db_path)
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)

    engine = create_engine(settings.db_path)
    await init_db(engine)
    session_factory = create_session_factory(engine)

    repo = SQLAlchemyEntryRepository(session_factory)
    feed_repo = SQLAlchemyFeedRepository(session_factory)
    config_repo = SQLAlchemyGuildConfigRepository(session_factory)
    llm = OllamaLLM(host=settings.ollama_host, model=settings.ollama_model)
    feed_fetcher = AiohttpFeedFetcher()

    store_entry = StoreEntryUseCase(repo)
    search_entries = SearchEntriesUseCase(repo)
    delete_entry = DeleteEntryUseCase(repo)
    list_by_tag = ListByTagUseCase(repo)
    ask_query = AskQueryUseCase(repo, llm)
    add_feed = AddFeedUseCase(feed_repo, settings.rss_bridge_url)
    remove_feed = RemoveFeedUseCase(feed_repo)
    list_feeds = ListFeedsUseCase(feed_repo)
    poll_feeds = PollFeedsUseCase(feed_repo, feed_fetcher)
    get_stats = GetStatsUseCase(repo, feed_repo)
    get_entry = GetEntryUseCase(repo)
    edit_entry = EditEntryUseCase(repo)
    list_all_entries = ListAllEntriesUseCase(repo)
    list_by_author = ListByAuthorUseCase(repo)
    purge_by_author = PurgeByAuthorUseCase(repo)
    purge_by_tag = PurgeByTagUseCase(repo)
    get_guild_config = GetGuildConfigUseCase(config_repo)
    set_guild_config = SetGuildConfigUseCase(config_repo)

    bot = LilwmanBot(
        guild_id=settings.discord_guild_id,
        store_entry=store_entry,
        search_entries=search_entries,
        delete_entry=delete_entry,
        list_by_tag=list_by_tag,
        ask_query=ask_query,
        add_feed=add_feed,
        remove_feed=remove_feed,
        list_feeds=list_feeds,
        poll_feeds=poll_feeds,
        get_stats=get_stats,
        get_entry=get_entry,
        edit_entry=edit_entry,
        list_all_entries=list_all_entries,
        list_by_author=list_by_author,
        purge_by_author=purge_by_author,
        purge_by_tag=purge_by_tag,
        get_guild_config=get_guild_config,
        set_guild_config=set_guild_config,
    )

    web_app = create_app(
        secret_key=settings.web_secret_key,
        client_id=settings.discord_client_id,
        client_secret=settings.discord_client_secret,
        web_base_url=settings.web_base_url,
        web_guild_id=settings.web_guild_id or str(settings.discord_guild_id),
        get_stats=get_stats,
        get_entry=get_entry,
        edit_entry=edit_entry,
        list_all_entries=list_all_entries,
        list_by_author=list_by_author,
        purge_by_author=purge_by_author,
        purge_by_tag=purge_by_tag,
        delete_entry=delete_entry,
        list_all_feeds=list_feeds,
        delete_feed=remove_feed,
        get_guild_config=get_guild_config,
        set_guild_config=set_guild_config,
    )

    web_server = uvicorn.Server(
        uvicorn.Config(web_app, host="0.0.0.0", port=settings.web_port, log_level="warning")
    )

    await asyncio.gather(
        bot.start(settings.discord_token),
        web_server.serve(),
    )


if __name__ == "__main__":
    asyncio.run(main())
