import pytest
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy import text

from lilwman.infrastructure.db.models import Base
from lilwman.infrastructure.db import feed_models as _feed_models  # noqa: F401
from lilwman.infrastructure.db import guild_config_models as _guild_config_models  # noqa: F401
from lilwman.infrastructure.db.feed_repository import SQLAlchemyFeedRepository


@pytest.fixture
async def session_factory(tmp_path):
    db_file = tmp_path / "test.db"
    engine = create_async_engine(f"sqlite+aiosqlite:///{db_file}")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.execute(text(
            """
            CREATE VIRTUAL TABLE IF NOT EXISTS entries_fts USING fts5(
                entry_id UNINDEXED,
                content,
                tags
            )
            """
        ))
    factory = async_sessionmaker(engine, expire_on_commit=False)
    yield factory
    await engine.dispose()


@pytest.fixture
def feed_repo(session_factory):
    return SQLAlchemyFeedRepository(session_factory)
