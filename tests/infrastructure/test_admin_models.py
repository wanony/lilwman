from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from lilwman.infrastructure.db.models import Base


async def test_guild_configs_table_created():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    table_names = list(Base.metadata.tables.keys())
    assert "guild_configs" in table_names
    await engine.dispose()


async def test_entries_has_guild_id_column():
    from lilwman.infrastructure.db.models import EntryModel
    cols = {c.name for c in EntryModel.__table__.columns}
    assert "guild_id" in cols


async def test_feed_subscriptions_has_guild_id_column():
    from lilwman.infrastructure.db.feed_models import FeedSubscriptionModel
    cols = {c.name for c in FeedSubscriptionModel.__table__.columns}
    assert "guild_id" in cols
