from sqlalchemy import text
from lilwman.infrastructure.db.session import create_engine, init_db


async def test_init_db_creates_feed_subscriptions(tmp_path):
    engine = create_engine(str(tmp_path / "test.db"))
    await init_db(engine)
    async with engine.connect() as conn:
        result = await conn.execute(
            text("SELECT name FROM sqlite_master WHERE type='table'")
        )
        tables = {row[0] for row in result.fetchall()}
    await engine.dispose()
    assert "feed_subscriptions" in tables


async def test_init_db_creates_seen_posts(tmp_path):
    engine = create_engine(str(tmp_path / "test.db"))
    await init_db(engine)
    async with engine.connect() as conn:
        result = await conn.execute(
            text("SELECT name FROM sqlite_master WHERE type='table'")
        )
        tables = {row[0] for row in result.fetchall()}
    await engine.dispose()
    assert "seen_posts" in tables


async def test_init_db_feed_tables_idempotent(tmp_path):
    engine = create_engine(str(tmp_path / "test.db"))
    await init_db(engine)
    await init_db(engine)  # second call must not raise
    await engine.dispose()
