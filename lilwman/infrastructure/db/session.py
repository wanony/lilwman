from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy import text

from .models import Base


def create_engine(db_path: str) -> AsyncEngine:
    return create_async_engine(f"sqlite+aiosqlite:///{db_path}", echo=False)


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False)


async def init_db(engine: AsyncEngine) -> None:
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
