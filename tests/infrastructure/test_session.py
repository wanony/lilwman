from sqlalchemy import text

from lilwman.infrastructure.db.session import create_engine, create_session_factory, init_db


async def test_create_engine_returns_async_engine(tmp_path):
    from sqlalchemy.ext.asyncio import AsyncEngine
    db_path = str(tmp_path / "test.db")
    engine = create_engine(db_path)
    assert isinstance(engine, AsyncEngine)
    await engine.dispose()


async def test_init_db_creates_entries_and_tags_tables(tmp_path):
    db_path = str(tmp_path / "test.db")
    engine = create_engine(db_path)
    await init_db(engine)

    async with engine.connect() as conn:
        result = await conn.execute(
            text("SELECT name FROM sqlite_master WHERE type='table'")
        )
        tables = {row[0] for row in result.fetchall()}

    assert "entries" in tables
    assert "tags" in tables
    await engine.dispose()


async def test_init_db_creates_fts5_virtual_table(tmp_path):
    db_path = str(tmp_path / "test.db")
    engine = create_engine(db_path)
    await init_db(engine)

    async with engine.connect() as conn:
        result = await conn.execute(
            text("SELECT name FROM sqlite_master WHERE type='table' AND name='entries_fts'")
        )
        row = result.fetchone()

    assert row is not None
    await engine.dispose()


async def test_init_db_is_idempotent(tmp_path):
    db_path = str(tmp_path / "test.db")
    engine = create_engine(db_path)
    await init_db(engine)
    await init_db(engine)  # second call must not raise
    await engine.dispose()


async def test_foreign_keys_pragma_enabled(tmp_path):
    engine = create_engine(str(tmp_path / "test.db"))
    async with engine.connect() as conn:
        result = await conn.execute(text("PRAGMA foreign_keys"))
        row = result.fetchone()
    await engine.dispose()
    assert row[0] == 1


async def test_create_session_factory_returns_working_session(tmp_path):
    db_path = str(tmp_path / "test.db")
    engine = create_engine(db_path)
    await init_db(engine)
    factory = create_session_factory(engine)

    async with factory() as session:
        assert session is not None

    await engine.dispose()
