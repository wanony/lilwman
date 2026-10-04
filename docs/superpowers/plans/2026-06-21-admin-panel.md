# Admin Panel Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a Discord `/admin` command group and a FastAPI web panel (Discord OAuth, Jinja2+Tailwind) for content moderation, stats, feed management, and per-guild configuration.

**Architecture:** 10 new application use cases and 2 new repositories share domain entities. The web panel (FastAPI+Jinja2) and Discord cog both call the same use cases via dependency injection. The web server runs alongside the bot via `asyncio.gather()`.

**Tech Stack:** Python 3.11+, discord.py 2.4+, SQLAlchemy async, aiosqlite, FastAPI, uvicorn, Jinja2, itsdangerous, aiohttp (OAuth), pytest-asyncio auto mode.

## Global Constraints

- Python ≥ 3.11
- pytest-asyncio `asyncio_mode = "auto"` — **NO `@pytest.mark.asyncio` on any test, ever**
- Clean arch: `domain/` stdlib only; `application/` domain+stdlib only; `infrastructure/` domain+stdlib+sqlalchemy/aiosqlite/aiohttp/fastapi/jinja2; `bot/` application+stdlib+discord; `__main__.py` and `config.py` exempt
- All bot commands check `guild_permissions.administrator` + `guild_id is not None` before acting
- All new code targets ≥85% test coverage
- No placeholder code — every step shows the exact implementation
- Run tests with: `uv run pytest -q`

---

## File Map

**New files:**
```
lilwman/domain/admin_entities.py
lilwman/domain/admin_ports.py
lilwman/infrastructure/db/guild_config_models.py
lilwman/infrastructure/db/migrations/versions/0003_admin.py
lilwman/infrastructure/db/guild_config_repo.py
lilwman/application/get_entry.py
lilwman/application/edit_entry.py
lilwman/application/list_by_author.py
lilwman/application/list_all_entries.py
lilwman/application/purge_by_author.py
lilwman/application/purge_by_tag.py
lilwman/application/get_stats.py
lilwman/application/get_guild_config.py
lilwman/application/set_guild_config.py
lilwman/bot/admin_views.py
lilwman/bot/commands/admin.py
lilwman/infrastructure/web/__init__.py
lilwman/infrastructure/web/app.py
lilwman/infrastructure/web/auth.py
lilwman/infrastructure/web/routes/__init__.py
lilwman/infrastructure/web/routes/dashboard.py
lilwman/infrastructure/web/routes/entries.py
lilwman/infrastructure/web/routes/feeds.py
lilwman/infrastructure/web/routes/config_route.py
lilwman/infrastructure/web/templates/base.html
lilwman/infrastructure/web/templates/login.html
lilwman/infrastructure/web/templates/dashboard.html
lilwman/infrastructure/web/templates/entries.html
lilwman/infrastructure/web/templates/entry_edit.html
lilwman/infrastructure/web/templates/feeds.html
lilwman/infrastructure/web/templates/config.html
tests/domain/test_admin_entities.py
tests/infrastructure/test_guild_config_repo.py
tests/infrastructure/test_web_auth.py
tests/infrastructure/test_web_routes.py
tests/application/test_moderation_use_cases.py
tests/application/test_stats_config_use_cases.py
tests/bot/test_admin_commands.py
tests/bot/test_admin_views.py
```

**Modified files:**
```
lilwman/domain/entities.py            — add guild_id: str = ""
lilwman/domain/ports.py               — add list_by_author, list_all, update, get_stats, purge_by_author, purge_by_tag abstract methods; guild_id on save
lilwman/domain/feed_entities.py       — add guild_id: str = "" to FeedSubscription
lilwman/domain/feed_ports.py          — guild_id on save; admin param on delete; count_for_guild
lilwman/infrastructure/db/models.py   — add guild_id column to EntryModel
lilwman/infrastructure/db/feed_models.py — add guild_id column to FeedSubscriptionModel
lilwman/infrastructure/db/session.py  — import guild_config_models
lilwman/infrastructure/db/repository.py — implement new abstract methods
lilwman/infrastructure/db/feed_repository.py — guild_id on save; admin on delete; count_for_guild
lilwman/application/store_entry.py    — add guild_id param
lilwman/application/add_feed.py       — add guild_id to execute() and execute_custom_url()
lilwman/bot/commands/store.py         — pass guild_id; check store_restricted
lilwman/bot/commands/feed.py          — pass guild_id on all write commands
lilwman/bot/bot.py                    — new use case params; AdminCog in setup_hook
lilwman/__main__.py                   — new use cases; asyncio.gather + uvicorn
lilwman/config.py                     — 6 new fields
pyproject.toml                        — add fastapi, uvicorn, jinja2, itsdangerous
.env.example                          — 6 new entries
tests/application/conftest.py         — import guild_config_models; guild_config_repo fixture
tests/infrastructure/conftest.py      — import guild_config_models; guild_config_repo fixture
tests/bot/test_bot.py                 — new use case kwargs in make_bot_instance()
tests/test_config.py                  — new config field tests
```

---

### Task 1: Domain entities and port extensions

**Files:**
- Create: `lilwman/domain/admin_entities.py`
- Create: `lilwman/domain/admin_ports.py`
- Modify: `lilwman/domain/entities.py`
- Modify: `lilwman/domain/ports.py`
- Modify: `lilwman/domain/feed_entities.py`
- Modify: `lilwman/domain/feed_ports.py`
- Test: `tests/domain/test_admin_entities.py`

**Interfaces:**
- Produces: `BotStats`, `GuildConfig` dataclasses; `GuildConfigRepository` ABC; updated `EntryRepository` ABC with `list_by_author`, `list_all`, `update`, `get_stats`, `purge_by_author`, `purge_by_tag`; updated `FeedRepository` ABC with `count_for_guild`; `Entry.guild_id`; `FeedSubscription.guild_id`

- [ ] **Step 1: Write the failing test**

```python
# tests/domain/test_admin_entities.py
from datetime import datetime, timezone
from lilwman.domain.admin_entities import BotStats, GuildConfig


def test_bot_stats_fields():
    stats = BotStats(
        total_entries=10,
        entries_this_week=3,
        entries_this_month=7,
        total_feeds=2,
        unique_tags=5,
        top_tags=[("python", 4), ("discord", 2)],
        top_authors=[("alice", 6), ("bob", 4)],
    )
    assert stats.total_entries == 10
    assert stats.entries_this_week == 3
    assert stats.top_tags[0] == ("python", 4)


def test_guild_config_defaults():
    now = datetime.now(timezone.utc)
    config = GuildConfig(guild_id="123", store_restricted=False, created_at=now, updated_at=now)
    assert config.store_restricted is False
    assert config.guild_id == "123"


def test_entry_guild_id_defaults_empty():
    from lilwman.domain.entities import Entry
    e = Entry(
        id=1, content="x", tags=[], author_id="1",
        author_name="a", created_at=now, updated_at=now,
    )
    assert e.guild_id == ""


def test_feed_subscription_guild_id_defaults_empty():
    from lilwman.domain.feed_entities import FeedSubscription
    sub = FeedSubscription(
        id=1, channel_id="c", platform="reddit",
        account_name="python", rss_url="http://x.com",
        created_at=now,
    )
    assert sub.guild_id == ""
```

- [ ] **Step 2: Run to verify fail**

```bash
uv run pytest tests/domain/test_admin_entities.py -v
```
Expected: `ModuleNotFoundError: No module named 'lilwman.domain.admin_entities'`

- [ ] **Step 3: Create `lilwman/domain/admin_entities.py`**

```python
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class BotStats:
    total_entries: int
    entries_this_week: int
    entries_this_month: int
    total_feeds: int
    unique_tags: int
    top_tags: list[tuple[str, int]] = field(default_factory=list)
    top_authors: list[tuple[str, int]] = field(default_factory=list)


@dataclass
class GuildConfig:
    guild_id: str
    store_restricted: bool
    created_at: datetime
    updated_at: datetime
```

- [ ] **Step 4: Create `lilwman/domain/admin_ports.py`**

```python
from abc import ABC, abstractmethod
from .admin_entities import GuildConfig


class GuildConfigRepository(ABC):
    @abstractmethod
    async def get(self, guild_id: str) -> GuildConfig: ...

    @abstractmethod
    async def save(self, guild_id: str, store_restricted: bool) -> GuildConfig: ...
```

- [ ] **Step 5: Update `lilwman/domain/entities.py`** — add `guild_id` field with default

```python
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class Entry:
    id: int
    content: str
    tags: list[str]
    author_id: str
    author_name: str
    created_at: datetime
    updated_at: datetime
    guild_id: str = ""
```

- [ ] **Step 6: Update `lilwman/domain/feed_entities.py`** — add `guild_id` to `FeedSubscription`

```python
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class FeedSubscription:
    id: int
    channel_id: str
    platform: str
    account_name: str
    rss_url: str
    created_at: datetime
    guild_id: str = ""


@dataclass
class FeedPost:
    guid: str
    title: str
    url: str
    description: str
    author: str
    published_at: datetime
    images: list[str] = field(default_factory=list)
    video_url: str | None = None
```

- [ ] **Step 7: Update `lilwman/domain/ports.py`** — add new abstract methods; add `guild_id` to `save`

```python
from abc import ABC, abstractmethod
from .entities import Entry


class EntryRepository(ABC):
    @abstractmethod
    async def save(
        self,
        content: str,
        tags: list[str],
        author_id: str,
        author_name: str,
        guild_id: str = "",
    ) -> Entry: ...

    @abstractmethod
    async def get_by_id(self, entry_id: int) -> Entry | None: ...

    @abstractmethod
    async def search(self, query: str, limit: int = 20) -> list[Entry]: ...

    @abstractmethod
    async def list_by_tag(self, tag: str) -> list[Entry]: ...

    @abstractmethod
    async def delete(self, entry_id: int, author_id: str, is_admin: bool) -> bool: ...

    @abstractmethod
    async def list_by_author(self, author_id: str, guild_id: str = "") -> list[Entry]: ...

    @abstractmethod
    async def list_all(
        self, guild_id: str = "", offset: int = 0, limit: int = 20
    ) -> tuple[list[Entry], int]: ...

    @abstractmethod
    async def update(self, entry_id: int, content: str, tags: list[str]) -> Entry | None: ...

    @abstractmethod
    async def get_stats(self, guild_id: str) -> dict: ...

    @abstractmethod
    async def purge_by_author(self, author_id: str, guild_id: str = "") -> int: ...

    @abstractmethod
    async def purge_by_tag(self, tag: str, guild_id: str = "") -> int: ...


class LLMPort(ABC):
    @abstractmethod
    async def generate(self, prompt: str) -> str: ...
```

- [ ] **Step 8: Update `lilwman/domain/feed_ports.py`** — add `guild_id` to `save`; add `admin` to `delete`; add `count_for_guild`

```python
from abc import ABC, abstractmethod
from .feed_entities import FeedSubscription, FeedPost


class FeedRepository(ABC):
    @abstractmethod
    async def save(
        self, channel_id: str, platform: str, account_name: str,
        rss_url: str, guild_id: str = "",
    ) -> FeedSubscription | None: ...

    @abstractmethod
    async def delete(self, feed_id: int, channel_id: str, admin: bool = False) -> bool: ...

    @abstractmethod
    async def list_for_channel(self, channel_id: str) -> list[FeedSubscription]: ...

    @abstractmethod
    async def list_all(self) -> list[FeedSubscription]: ...

    @abstractmethod
    async def is_seen(self, feed_id: int, guid: str) -> bool: ...

    @abstractmethod
    async def mark_seen(self, feed_id: int, guid: str) -> None: ...

    @abstractmethod
    async def prune_seen(self, older_than_days: int) -> None: ...

    @abstractmethod
    async def count_for_guild(self, guild_id: str) -> int: ...


class FeedFetcher(ABC):
    @abstractmethod
    async def fetch(self, url: str) -> list[FeedPost]: ...
```

- [ ] **Step 9: Run tests**

```bash
uv run pytest tests/domain/ -v
```
Expected: all domain tests pass.

- [ ] **Step 10: Commit**

```bash
git add lilwman/domain/admin_entities.py lilwman/domain/admin_ports.py \
        lilwman/domain/entities.py lilwman/domain/ports.py \
        lilwman/domain/feed_entities.py lilwman/domain/feed_ports.py \
        tests/domain/test_admin_entities.py
git commit -m "feat: add admin domain entities, extend ports for moderation + stats"
```

---

### Task 2: Migration 0003 + ORM models

**Files:**
- Create: `lilwman/infrastructure/db/guild_config_models.py`
- Create: `lilwman/infrastructure/db/migrations/versions/0003_admin.py`
- Modify: `lilwman/infrastructure/db/models.py`
- Modify: `lilwman/infrastructure/db/feed_models.py`
- Modify: `lilwman/infrastructure/db/session.py`
- Modify: `tests/application/conftest.py`
- Modify: `tests/infrastructure/conftest.py`

**Interfaces:**
- Consumes: `Base` from `models.py`; `GuildConfig` from `admin_entities.py`
- Produces: `GuildConfigModel` ORM class; `guild_id` column on `EntryModel` and `FeedSubscriptionModel`

- [ ] **Step 1: Write the failing test**

```python
# tests/infrastructure/test_admin_models.py
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
```

- [ ] **Step 2: Run to verify fail**

```bash
uv run pytest tests/infrastructure/test_admin_models.py -v
```
Expected: `AssertionError: assert "guild_configs" in ...`

- [ ] **Step 3: Create `lilwman/infrastructure/db/guild_config_models.py`**

```python
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from .models import Base


class GuildConfigModel(Base):
    __tablename__ = "guild_configs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    guild_id: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    store_restricted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
```

- [ ] **Step 4: Update `lilwman/infrastructure/db/models.py`** — add `guild_id` to `EntryModel`

```python
from datetime import datetime
from sqlalchemy import Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class EntryModel(Base):
    __tablename__ = "entries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    author_id: Mapped[str] = mapped_column(String, nullable=False)
    author_name: Mapped[str] = mapped_column(String, nullable=False)
    guild_id: Mapped[str] = mapped_column(String, nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    tags: Mapped[list["TagModel"]] = relationship(
        back_populates="entry", cascade="all, delete-orphan"
    )


class TagModel(Base):
    __tablename__ = "tags"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    entry_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("entries.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String, nullable=False)

    entry: Mapped["EntryModel"] = relationship(back_populates="tags")
```

- [ ] **Step 5: Update `lilwman/infrastructure/db/feed_models.py`** — add `guild_id` to `FeedSubscriptionModel`

```python
from datetime import datetime

from sqlalchemy import Integer, String, DateTime, ForeignKey, UniqueConstraint, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .models import Base


class FeedSubscriptionModel(Base):
    __tablename__ = "feed_subscriptions"
    __table_args__ = (
        UniqueConstraint("channel_id", "rss_url", name="uq_channel_rss_url"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    channel_id: Mapped[str] = mapped_column(String, nullable=False)
    guild_id: Mapped[str] = mapped_column(String, nullable=False, default="")
    platform: Mapped[str] = mapped_column(String, nullable=False)
    account_name: Mapped[str] = mapped_column(String, nullable=False)
    rss_url: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    seen_posts: Mapped[list["SeenPostModel"]] = relationship(
        back_populates="subscription", cascade="all, delete-orphan"
    )


class SeenPostModel(Base):
    __tablename__ = "seen_posts"
    __table_args__ = (
        Index("ix_seen_posts_feed_guid", "feed_id", "guid"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    feed_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("feed_subscriptions.id", ondelete="CASCADE"), nullable=False
    )
    guid: Mapped[str] = mapped_column(String, nullable=False)
    seen_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    subscription: Mapped["FeedSubscriptionModel"] = relationship(back_populates="seen_posts")
```

- [ ] **Step 6: Update `lilwman/infrastructure/db/session.py`** — import `guild_config_models`

```python
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy import event, text

from .models import Base
from . import feed_models as _feed_models  # noqa: F401
from . import guild_config_models as _guild_config_models  # noqa: F401


def create_engine(db_path: str) -> AsyncEngine:
    engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}", echo=False)

    @event.listens_for(engine.sync_engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    return engine


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
```

- [ ] **Step 7: Create migration `lilwman/infrastructure/db/migrations/versions/0003_admin.py`**

```python
"""add guild_configs table, guild_id to entries and feed_subscriptions

Revision ID: 0003
Revises: 0002
Create Date: 2026-06-21
"""
from typing import Sequence, Union
import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "guild_configs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("guild_id", sa.String(), nullable=False, unique=True),
        sa.Column("store_restricted", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.add_column("entries", sa.Column("guild_id", sa.String(), nullable=False, server_default=""))
    op.add_column("feed_subscriptions", sa.Column("guild_id", sa.String(), nullable=False, server_default=""))


def downgrade() -> None:
    op.drop_column("feed_subscriptions", "guild_id")
    op.drop_column("entries", "guild_id")
    op.drop_table("guild_configs")
```

- [ ] **Step 8: Update both conftest files** — add `guild_config_models` import and fixture

`tests/application/conftest.py` — add after existing feed_models import:
```python
from lilwman.infrastructure.db import guild_config_models as _guild_config_models  # noqa: F401
from lilwman.infrastructure.db.guild_config_repo import SQLAlchemyGuildConfigRepository

# add at end:
@pytest.fixture
def guild_config_repo(session_factory):
    return SQLAlchemyGuildConfigRepository(session_factory)
```

`tests/infrastructure/conftest.py` — same additions.

Full updated `tests/application/conftest.py`:
```python
import pytest
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy import text

from lilwman.infrastructure.db.models import Base
from lilwman.infrastructure.db import feed_models as _feed_models  # noqa: F401
from lilwman.infrastructure.db import guild_config_models as _guild_config_models  # noqa: F401
from lilwman.infrastructure.db.repository import SQLAlchemyEntryRepository
from lilwman.infrastructure.db.feed_repository import SQLAlchemyFeedRepository
from lilwman.infrastructure.db.guild_config_repo import SQLAlchemyGuildConfigRepository


@pytest.fixture
async def session_factory():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
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
def repo(session_factory):
    return SQLAlchemyEntryRepository(session_factory)


@pytest.fixture
def feed_repo(session_factory):
    return SQLAlchemyFeedRepository(session_factory)


@pytest.fixture
def guild_config_repo(session_factory):
    return SQLAlchemyGuildConfigRepository(session_factory)
```

Apply the same changes to `tests/infrastructure/conftest.py`.

- [ ] **Step 9: Run tests**

```bash
uv run pytest tests/infrastructure/test_admin_models.py -v
```
Expected: all 3 tests pass.

- [ ] **Step 10: Commit**

```bash
git add lilwman/infrastructure/db/guild_config_models.py \
        lilwman/infrastructure/db/migrations/versions/0003_admin.py \
        lilwman/infrastructure/db/models.py \
        lilwman/infrastructure/db/feed_models.py \
        lilwman/infrastructure/db/session.py \
        tests/infrastructure/test_admin_models.py \
        tests/application/conftest.py \
        tests/infrastructure/conftest.py
git commit -m "feat: add guild_configs table, guild_id columns (migration 0003)"
```

---

### Task 3: Repository implementations — entry extensions + guild_config repo

**Files:**
- Modify: `lilwman/infrastructure/db/repository.py`
- Create: `lilwman/infrastructure/db/guild_config_repo.py`
- Test: `tests/infrastructure/test_guild_config_repo.py` (new)
- Test: add to `tests/infrastructure/test_repository.py`

**Interfaces:**
- Consumes: updated `EntryRepository` ABC from Task 1; `GuildConfigRepository` ABC from Task 1; `GuildConfigModel` from Task 2
- Produces: `SQLAlchemyEntryRepository` with 6 new methods; `SQLAlchemyGuildConfigRepository`

- [ ] **Step 1: Write failing tests for new entry repo methods**

Add to `tests/infrastructure/test_repository.py`:

```python
async def test_list_by_author_returns_entries_for_author(repo):
    await repo.save("entry 1", [], "user1", "Alice", guild_id="g1")
    await repo.save("entry 2", [], "user2", "Bob", guild_id="g1")
    await repo.save("entry 3", [], "user1", "Alice", guild_id="g1")
    results = await repo.list_by_author("user1")
    assert len(results) == 2
    assert all(e.author_id == "user1" for e in results)


async def test_list_all_returns_paginated(repo):
    for i in range(5):
        await repo.save(f"entry {i}", [], "user1", "Alice")
    entries, total = await repo.list_all(offset=0, limit=3)
    assert total == 5
    assert len(entries) == 3


async def test_update_changes_content_and_tags(repo):
    entry = await repo.save("original", ["old"], "user1", "Alice")
    updated = await repo.update(entry.id, "updated content", ["new", "tag"])
    assert updated is not None
    assert updated.content == "updated content"
    assert updated.tags == ["new", "tag"]


async def test_update_nonexistent_returns_none(repo):
    result = await repo.update(9999, "x", [])
    assert result is None


async def test_get_stats_counts_entries(repo):
    await repo.save("e1", ["python"], "u1", "Alice", guild_id="g1")
    await repo.save("e2", ["python", "discord"], "u2", "Bob", guild_id="g1")
    stats = await repo.get_stats("g1")
    assert stats["total_entries"] == 2
    assert stats["unique_tags"] == 2
    assert len(stats["top_tags"]) >= 1


async def test_purge_by_author_deletes_entries(repo):
    await repo.save("e1", [], "user1", "Alice")
    await repo.save("e2", [], "user1", "Alice")
    await repo.save("e3", [], "user2", "Bob")
    count = await repo.purge_by_author("user1")
    assert count == 2
    entries, total = await repo.list_all()
    assert total == 1


async def test_purge_by_tag_deletes_entries(repo):
    await repo.save("e1", ["spam"], "u1", "Alice")
    await repo.save("e2", ["spam", "other"], "u2", "Bob")
    await repo.save("e3", ["other"], "u3", "Carol")
    count = await repo.purge_by_tag("spam")
    assert count == 2
    entries, total = await repo.list_all()
    assert total == 1
```

- [ ] **Step 2: Write failing test for guild_config repo**

```python
# tests/infrastructure/test_guild_config_repo.py
from lilwman.infrastructure.db.guild_config_repo import SQLAlchemyGuildConfigRepository


async def test_get_returns_default_when_not_found(guild_config_repo):
    config = await guild_config_repo.get("unknown_guild")
    assert config.guild_id == "unknown_guild"
    assert config.store_restricted is False


async def test_save_and_get_roundtrip(guild_config_repo):
    await guild_config_repo.save("guild1", store_restricted=True)
    config = await guild_config_repo.get("guild1")
    assert config.store_restricted is True


async def test_save_overwrites_existing(guild_config_repo):
    await guild_config_repo.save("guild1", store_restricted=True)
    await guild_config_repo.save("guild1", store_restricted=False)
    config = await guild_config_repo.get("guild1")
    assert config.store_restricted is False
```

- [ ] **Step 3: Run to verify fail**

```bash
uv run pytest tests/infrastructure/test_repository.py::test_list_by_author_returns_entries_for_author \
             tests/infrastructure/test_guild_config_repo.py -v
```
Expected: `AttributeError` — methods not yet implemented.

- [ ] **Step 4: Implement new methods in `lilwman/infrastructure/db/repository.py`**

The existing file already has `save`, `get_by_id`, `search`, `list_by_tag`, `delete`, `_to_entity`. Add these methods inside `SQLAlchemyEntryRepository`:

```python
    async def list_by_author(self, author_id: str, guild_id: str = "") -> list[Entry]:
        async with self._session_factory() as session:
            q = (
                select(EntryModel)
                .options(selectinload(EntryModel.tags))
                .where(EntryModel.author_id == author_id)
                .order_by(EntryModel.created_at.desc())
            )
            if guild_id:
                q = q.where(EntryModel.guild_id == guild_id)
            result = await session.execute(q)
            return [self._to_entity(m) for m in result.scalars().unique().all()]

    async def list_all(
        self, guild_id: str = "", offset: int = 0, limit: int = 20
    ) -> tuple[list[Entry], int]:
        from sqlalchemy import func
        async with self._session_factory() as session:
            count_q = select(func.count(EntryModel.id))
            q = (
                select(EntryModel)
                .options(selectinload(EntryModel.tags))
                .order_by(EntryModel.created_at.desc())
                .offset(offset)
                .limit(limit)
            )
            if guild_id:
                count_q = count_q.where(EntryModel.guild_id == guild_id)
                q = q.where(EntryModel.guild_id == guild_id)
            total = (await session.execute(count_q)).scalar() or 0
            result = await session.execute(q)
            return [self._to_entity(m) for m in result.scalars().unique().all()], total

    async def update(self, entry_id: int, content: str, tags: list[str]) -> Entry | None:
        now = datetime.now(timezone.utc)
        clean_tags = [t.strip().lower() for t in tags if t.strip()]
        async with self._session_factory() as session:
            async with session.begin():
                result = await session.execute(
                    select(EntryModel)
                    .options(selectinload(EntryModel.tags))
                    .where(EntryModel.id == entry_id)
                )
                model = result.scalar_one_or_none()
                if model is None:
                    return None
                model.content = content
                model.updated_at = now
                for tag in list(model.tags):
                    await session.delete(tag)
                await session.flush()
                session.add_all(
                    TagModel(entry_id=model.id, name=t) for t in clean_tags
                )
                await session.execute(
                    text("DELETE FROM entries_fts WHERE entry_id = :eid"),
                    {"eid": entry_id},
                )
                tags_str = " ".join(clean_tags)
                await session.execute(
                    text(
                        "INSERT INTO entries_fts(entry_id, content, tags) "
                        "VALUES (:eid, :c, :t)"
                    ),
                    {"eid": entry_id, "c": content, "t": tags_str},
                )
        return Entry(
            id=model.id,
            content=content,
            tags=clean_tags,
            author_id=model.author_id,
            author_name=model.author_name,
            guild_id=model.guild_id,
            created_at=model.created_at,
            updated_at=now,
        )

    async def get_stats(self, guild_id: str) -> dict:
        from datetime import timedelta
        from sqlalchemy import func
        now = datetime.now(timezone.utc)
        week_ago = now - timedelta(days=7)
        month_ago = now - timedelta(days=30)

        async with self._session_factory() as session:
            def _gf(q):
                return q.where(EntryModel.guild_id == guild_id) if guild_id else q

            total = (await session.execute(_gf(select(func.count(EntryModel.id))))).scalar() or 0

            week_q = select(func.count(EntryModel.id)).where(EntryModel.created_at >= week_ago)
            entries_this_week = (await session.execute(_gf(week_q))).scalar() or 0

            month_q = select(func.count(EntryModel.id)).where(EntryModel.created_at >= month_ago)
            entries_this_month = (await session.execute(_gf(month_q))).scalar() or 0

            tag_count_q = select(func.count(func.distinct(TagModel.name))).join(
                EntryModel, TagModel.entry_id == EntryModel.id
            )
            unique_tags = (await session.execute(_gf(tag_count_q))).scalar() or 0

            top_tags_q = (
                select(TagModel.name, func.count(TagModel.id).label("cnt"))
                .join(EntryModel, TagModel.entry_id == EntryModel.id)
                .group_by(TagModel.name)
                .order_by(func.count(TagModel.id).desc())
                .limit(10)
            )
            if guild_id:
                top_tags_q = top_tags_q.where(EntryModel.guild_id == guild_id)
            top_tags = [(r[0], r[1]) for r in (await session.execute(top_tags_q)).fetchall()]

            top_authors_q = (
                select(EntryModel.author_name, func.count(EntryModel.id).label("cnt"))
                .group_by(EntryModel.author_name)
                .order_by(func.count(EntryModel.id).desc())
                .limit(10)
            )
            top_authors = [(r[0], r[1]) for r in (await session.execute(_gf(top_authors_q))).fetchall()]

        return {
            "total_entries": total,
            "entries_this_week": entries_this_week,
            "entries_this_month": entries_this_month,
            "unique_tags": unique_tags,
            "top_tags": top_tags,
            "top_authors": top_authors,
        }

    async def purge_by_author(self, author_id: str, guild_id: str = "") -> int:
        from sqlalchemy import delete as sa_delete
        async with self._session_factory() as session:
            async with session.begin():
                q = select(EntryModel.id).where(EntryModel.author_id == author_id)
                if guild_id:
                    q = q.where(EntryModel.guild_id == guild_id)
                ids = [r[0] for r in (await session.execute(q)).fetchall()]
                if not ids:
                    return 0
                for eid in ids:
                    await session.execute(
                        text("DELETE FROM entries_fts WHERE entry_id = :eid"), {"eid": eid}
                    )
                await session.execute(sa_delete(EntryModel).where(EntryModel.id.in_(ids)))
                return len(ids)

    async def purge_by_tag(self, tag: str, guild_id: str = "") -> int:
        from sqlalchemy import delete as sa_delete
        clean_tag = tag.strip().lower()
        async with self._session_factory() as session:
            async with session.begin():
                q = (
                    select(EntryModel.id)
                    .join(TagModel, EntryModel.id == TagModel.entry_id)
                    .where(TagModel.name == clean_tag)
                )
                if guild_id:
                    q = q.where(EntryModel.guild_id == guild_id)
                ids = [r[0] for r in (await session.execute(q)).fetchall()]
                if not ids:
                    return 0
                for eid in ids:
                    await session.execute(
                        text("DELETE FROM entries_fts WHERE entry_id = :eid"), {"eid": eid}
                    )
                await session.execute(sa_delete(EntryModel).where(EntryModel.id.in_(ids)))
                return len(ids)
```

Also update the existing `save` method signature to accept `guild_id`:

```python
    async def save(
        self,
        content: str,
        tags: list[str],
        author_id: str,
        author_name: str,
        guild_id: str = "",
    ) -> Entry:
        now = datetime.now(timezone.utc)
        clean_tags = [t.strip().lower() for t in tags if t.strip()]
        async with self._session_factory() as session:
            async with session.begin():
                entry_model = EntryModel(
                    content=content,
                    author_id=author_id,
                    author_name=author_name,
                    guild_id=guild_id,
                    created_at=now,
                    updated_at=now,
                )
                session.add(entry_model)
                await session.flush()

                if clean_tags:
                    session.add_all(
                        TagModel(entry_id=entry_model.id, name=t) for t in clean_tags
                    )

                tags_str = " ".join(clean_tags)
                await session.execute(
                    text(
                        "INSERT INTO entries_fts(entry_id, content, tags) "
                        "VALUES (:eid, :c, :t)"
                    ),
                    {"eid": entry_model.id, "c": content, "t": tags_str},
                )

        return Entry(
            id=entry_model.id,
            content=content,
            tags=clean_tags,
            author_id=author_id,
            author_name=author_name,
            guild_id=guild_id,
            created_at=now,
            updated_at=now,
        )
```

- [ ] **Step 5: Create `lilwman/infrastructure/db/guild_config_repo.py`**

```python
from datetime import datetime, timezone

from sqlalchemy import select

from lilwman.domain.admin_entities import GuildConfig
from lilwman.domain.admin_ports import GuildConfigRepository
from .guild_config_models import GuildConfigModel


class SQLAlchemyGuildConfigRepository(GuildConfigRepository):
    def __init__(self, session_factory) -> None:
        self._session_factory = session_factory

    async def get(self, guild_id: str) -> GuildConfig:
        async with self._session_factory() as session:
            result = await session.execute(
                select(GuildConfigModel).where(GuildConfigModel.guild_id == guild_id)
            )
            model = result.scalar_one_or_none()
            if model is None:
                now = datetime.now(timezone.utc)
                return GuildConfig(
                    guild_id=guild_id, store_restricted=False,
                    created_at=now, updated_at=now,
                )
            return self._to_entity(model)

    async def save(self, guild_id: str, store_restricted: bool) -> GuildConfig:
        now = datetime.now(timezone.utc)
        async with self._session_factory() as session:
            async with session.begin():
                result = await session.execute(
                    select(GuildConfigModel).where(GuildConfigModel.guild_id == guild_id)
                )
                model = result.scalar_one_or_none()
                if model is None:
                    model = GuildConfigModel(
                        guild_id=guild_id,
                        store_restricted=store_restricted,
                        created_at=now,
                        updated_at=now,
                    )
                    session.add(model)
                else:
                    model.store_restricted = store_restricted
                    model.updated_at = now
        return GuildConfig(
            guild_id=guild_id, store_restricted=store_restricted,
            created_at=model.created_at, updated_at=now,
        )

    def _to_entity(self, model: GuildConfigModel) -> GuildConfig:
        return GuildConfig(
            guild_id=model.guild_id,
            store_restricted=model.store_restricted,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )
```

- [ ] **Step 6: Run tests**

```bash
uv run pytest tests/infrastructure/test_repository.py tests/infrastructure/test_guild_config_repo.py -v
```
Expected: all new tests pass, existing tests still pass.

- [ ] **Step 7: Commit**

```bash
git add lilwman/infrastructure/db/repository.py \
        lilwman/infrastructure/db/guild_config_repo.py \
        tests/infrastructure/test_guild_config_repo.py
git commit -m "feat: implement entry repo extensions and guild config repository"
```

---

### Task 4: Feed repository guild_id threading + feed use case updates

**Files:**
- Modify: `lilwman/infrastructure/db/feed_repository.py`
- Modify: `lilwman/application/add_feed.py`
- Modify: `lilwman/bot/commands/feed.py`

**Interfaces:**
- Consumes: updated `FeedRepository` ABC from Task 1 (`guild_id` on `save`; `admin` on `delete`; `count_for_guild`)
- Produces: `AddFeedUseCase.execute(channel_id, platform, account_name, guild_id="")` and `execute_custom_url(channel_id, rss_url, guild_id="")` with guild_id; `FeedSubscription.guild_id` populated in DB

- [ ] **Step 1: Write failing tests**

Add to `tests/infrastructure/test_feed_repository.py`:
```python
async def test_save_stores_guild_id(feed_repo):
    sub = await feed_repo.save("ch1", "reddit", "python", "http://x.com", guild_id="g1")
    assert sub is not None
    assert sub.guild_id == "g1"


async def test_count_for_guild_returns_correct_count(feed_repo):
    await feed_repo.save("ch1", "reddit", "python", "http://a.com", guild_id="g1")
    await feed_repo.save("ch2", "twitter", "test", "http://b.com", guild_id="g1")
    await feed_repo.save("ch3", "reddit", "other", "http://c.com", guild_id="g2")
    assert await feed_repo.count_for_guild("g1") == 2
    assert await feed_repo.count_for_guild("g2") == 1


async def test_delete_admin_bypasses_channel_check(feed_repo):
    sub = await feed_repo.save("ch1", "reddit", "python", "http://x.com", guild_id="g1")
    deleted = await feed_repo.delete(sub.id, channel_id="different_channel", admin=True)
    assert deleted is True
```

Add to `tests/application/test_add_feed.py`:
```python
async def test_execute_passes_guild_id_to_repo(feed_repo):
    from lilwman.application.add_feed import AddFeedUseCase
    uc = AddFeedUseCase(feed_repo, "http://bridge.local")
    sub = await uc.execute("ch1", "reddit", "python", guild_id="g123")
    assert sub is not None
    assert sub.guild_id == "g123"
```

- [ ] **Step 2: Run to verify fail**

```bash
uv run pytest tests/infrastructure/test_feed_repository.py::test_save_stores_guild_id \
             tests/application/test_add_feed.py::test_execute_passes_guild_id_to_repo -v
```
Expected: `TypeError` — unexpected keyword argument `guild_id`.

- [ ] **Step 3: Update `lilwman/infrastructure/db/feed_repository.py`**

Update `save()` to accept and store `guild_id`:
```python
    async def save(
        self, channel_id: str, platform: str, account_name: str,
        rss_url: str, guild_id: str = "",
    ) -> FeedSubscription | None:
        now = datetime.now(timezone.utc)
        model = FeedSubscriptionModel(
            channel_id=channel_id,
            guild_id=guild_id,
            platform=platform,
            account_name=account_name,
            rss_url=rss_url,
            created_at=now,
        )
        async with self._session_factory() as session:
            async with session.begin():
                session.add(model)
                try:
                    await session.flush()
                except IntegrityError:
                    return None
        return FeedSubscription(
            id=model.id,
            channel_id=channel_id,
            guild_id=guild_id,
            platform=platform,
            account_name=account_name,
            rss_url=rss_url,
            created_at=now,
        )
```

Update `delete()` to support `admin` bypass:
```python
    async def delete(self, feed_id: int, channel_id: str, admin: bool = False) -> bool:
        async with self._session_factory() as session:
            async with session.begin():
                if admin:
                    result = await session.execute(
                        select(FeedSubscriptionModel).where(FeedSubscriptionModel.id == feed_id)
                    )
                else:
                    result = await session.execute(
                        select(FeedSubscriptionModel).where(
                            FeedSubscriptionModel.id == feed_id,
                            FeedSubscriptionModel.channel_id == channel_id,
                        )
                    )
                model = result.scalar_one_or_none()
                if model is None:
                    return False
                await session.delete(model)
                return True
```

Add `count_for_guild()`:
```python
    async def count_for_guild(self, guild_id: str) -> int:
        from sqlalchemy import func
        async with self._session_factory() as session:
            q = select(func.count(FeedSubscriptionModel.id))
            if guild_id:
                q = q.where(FeedSubscriptionModel.guild_id == guild_id)
            return (await session.execute(q)).scalar() or 0
```

- [ ] **Step 4: Update `lilwman/application/add_feed.py`** — add `guild_id` to both execute methods

```python
from urllib.parse import urlparse

from lilwman.domain.feed_entities import FeedSubscription
from lilwman.domain.feed_ports import FeedRepository

_BRIDGES: dict[str, str] = {
    "instagram":  "Instagram&username={account}",
    "tiktok":     "TikTok&username={account}",
    "twitter":    "Twitter&u={account}",
    "reddit":     "Reddit&r={account}",
    "youtube":    "YouTube&channel={account}",
    "twitch":     "Twitch&channel={account}",
    "hackernews": "HackerNews&category={account}",
}

SUPPORTED_PLATFORMS: set[str] = set(_BRIDGES.keys())


def build_rss_url(rss_bridge_host: str, platform: str, account: str) -> str:
    bridge_params = _BRIDGES[platform].format(account=account)
    return f"{rss_bridge_host}/?action=display&bridge={bridge_params}&format=Atom"


class AddFeedUseCase:
    def __init__(self, repo: FeedRepository, rss_bridge_url: str) -> None:
        self._repo = repo
        self._rss_bridge_url = rss_bridge_url

    async def execute(
        self, channel_id: str, platform: str, account_name: str, guild_id: str = ""
    ) -> FeedSubscription | None:
        rss_url = build_rss_url(self._rss_bridge_url, platform, account_name)
        return await self._repo.save(channel_id, platform, account_name, rss_url, guild_id=guild_id)

    async def execute_custom_url(
        self, channel_id: str, rss_url: str, guild_id: str = ""
    ) -> FeedSubscription | None:
        account_name = urlparse(rss_url).netloc or rss_url
        return await self._repo.save(channel_id, "custom", account_name, rss_url, guild_id=guild_id)
```

- [ ] **Step 5: Update `lilwman/bot/commands/feed.py`** — pass `guild_id` on add/addurl

In `feed_add`, change the execute call:
```python
        channel_id = str(interaction.channel_id)
        guild_id = str(interaction.guild_id) if interaction.guild_id else ""
        sub = await self.bot.add_feed.execute(channel_id, platform, account, guild_id=guild_id)
```

In `feed_addurl`, change the execute_custom_url call:
```python
        channel_id = str(interaction.channel_id)
        guild_id = str(interaction.guild_id) if interaction.guild_id else ""
        sub = await self.bot.add_feed.execute_custom_url(channel_id, url, guild_id=guild_id)
```

- [ ] **Step 6: Run tests**

```bash
uv run pytest tests/infrastructure/test_feed_repository.py \
             tests/application/test_add_feed.py \
             tests/bot/test_feed_commands.py -v
```
Expected: all pass.

- [ ] **Step 7: Commit**

```bash
git add lilwman/infrastructure/db/feed_repository.py \
        lilwman/application/add_feed.py \
        lilwman/bot/commands/feed.py
git commit -m "feat: thread guild_id through feed repository and add_feed use case"
```

---

### Task 5: Moderation use cases

**Files:**
- Create: `lilwman/application/get_entry.py`
- Create: `lilwman/application/edit_entry.py`
- Create: `lilwman/application/list_by_author.py`
- Create: `lilwman/application/list_all_entries.py`
- Create: `lilwman/application/purge_by_author.py`
- Create: `lilwman/application/purge_by_tag.py`
- Test: `tests/application/test_moderation_use_cases.py`

**Interfaces:**
- Consumes: updated `EntryRepository` from Tasks 1+3
- Produces: 6 use cases with these signatures:
  - `GetEntryUseCase(repo).execute(entry_id) -> Entry | None`
  - `EditEntryUseCase(repo).execute(entry_id, content, tags) -> Entry | None`
  - `ListByAuthorUseCase(repo).execute(author_id, guild_id="") -> list[Entry]`
  - `ListAllEntriesUseCase(repo).execute(guild_id="", page=1, per_page=20) -> tuple[list[Entry], int]`
  - `PurgeByAuthorUseCase(repo).execute(author_id, guild_id="") -> int`
  - `PurgeByTagUseCase(repo).execute(tag, guild_id="") -> int`

- [ ] **Step 1: Write failing tests**

```python
# tests/application/test_moderation_use_cases.py
import pytest
from lilwman.application.get_entry import GetEntryUseCase
from lilwman.application.edit_entry import EditEntryUseCase
from lilwman.application.list_by_author import ListByAuthorUseCase
from lilwman.application.list_all_entries import ListAllEntriesUseCase
from lilwman.application.purge_by_author import PurgeByAuthorUseCase
from lilwman.application.purge_by_tag import PurgeByTagUseCase


async def test_get_entry_returns_entry(repo):
    entry = await repo.save("hello", ["tag1"], "u1", "Alice")
    result = await GetEntryUseCase(repo).execute(entry.id)
    assert result is not None
    assert result.content == "hello"


async def test_get_entry_missing_returns_none(repo):
    result = await GetEntryUseCase(repo).execute(9999)
    assert result is None


async def test_edit_entry_updates_content_and_tags(repo):
    entry = await repo.save("original", ["old"], "u1", "Alice")
    result = await EditEntryUseCase(repo).execute(entry.id, "new content", ["new", "tag"])
    assert result is not None
    assert result.content == "new content"
    assert set(result.tags) == {"new", "tag"}


async def test_edit_entry_missing_returns_none(repo):
    result = await EditEntryUseCase(repo).execute(9999, "x", [])
    assert result is None


async def test_list_by_author_filters_correctly(repo):
    await repo.save("e1", [], "user1", "Alice")
    await repo.save("e2", [], "user2", "Bob")
    results = await ListByAuthorUseCase(repo).execute("user1")
    assert len(results) == 1
    assert results[0].author_id == "user1"


async def test_list_all_entries_pagination(repo):
    for i in range(5):
        await repo.save(f"entry {i}", [], "u1", "Alice")
    entries, total = await ListAllEntriesUseCase(repo).execute(page=1, per_page=3)
    assert total == 5
    assert len(entries) == 3
    entries_p2, _ = await ListAllEntriesUseCase(repo).execute(page=2, per_page=3)
    assert len(entries_p2) == 2


async def test_purge_by_author_returns_count(repo):
    await repo.save("e1", [], "u1", "Alice")
    await repo.save("e2", [], "u1", "Alice")
    await repo.save("e3", [], "u2", "Bob")
    count = await PurgeByAuthorUseCase(repo).execute("u1")
    assert count == 2
    _, total = await ListAllEntriesUseCase(repo).execute()
    assert total == 1


async def test_purge_by_tag_returns_count(repo):
    await repo.save("e1", ["spam"], "u1", "Alice")
    await repo.save("e2", ["spam", "ok"], "u2", "Bob")
    await repo.save("e3", ["ok"], "u3", "Carol")
    count = await PurgeByTagUseCase(repo).execute("spam")
    assert count == 2
    _, total = await ListAllEntriesUseCase(repo).execute()
    assert total == 1
```

- [ ] **Step 2: Run to verify fail**

```bash
uv run pytest tests/application/test_moderation_use_cases.py -v
```
Expected: `ModuleNotFoundError` — use case modules missing.

- [ ] **Step 3: Create all 6 use case files**

`lilwman/application/get_entry.py`:
```python
from lilwman.domain.entities import Entry
from lilwman.domain.ports import EntryRepository


class GetEntryUseCase:
    def __init__(self, repo: EntryRepository) -> None:
        self._repo = repo

    async def execute(self, entry_id: int) -> Entry | None:
        return await self._repo.get_by_id(entry_id)
```

`lilwman/application/edit_entry.py`:
```python
from lilwman.domain.entities import Entry
from lilwman.domain.ports import EntryRepository


class EditEntryUseCase:
    def __init__(self, repo: EntryRepository) -> None:
        self._repo = repo

    async def execute(self, entry_id: int, content: str, tags: list[str]) -> Entry | None:
        return await self._repo.update(entry_id, content, tags)
```

`lilwman/application/list_by_author.py`:
```python
from lilwman.domain.entities import Entry
from lilwman.domain.ports import EntryRepository


class ListByAuthorUseCase:
    def __init__(self, repo: EntryRepository) -> None:
        self._repo = repo

    async def execute(self, author_id: str, guild_id: str = "") -> list[Entry]:
        return await self._repo.list_by_author(author_id, guild_id=guild_id)
```

`lilwman/application/list_all_entries.py`:
```python
from lilwman.domain.entities import Entry
from lilwman.domain.ports import EntryRepository


class ListAllEntriesUseCase:
    def __init__(self, repo: EntryRepository) -> None:
        self._repo = repo

    async def execute(
        self, guild_id: str = "", page: int = 1, per_page: int = 20
    ) -> tuple[list[Entry], int]:
        offset = (page - 1) * per_page
        return await self._repo.list_all(guild_id=guild_id, offset=offset, limit=per_page)
```

`lilwman/application/purge_by_author.py`:
```python
from lilwman.domain.ports import EntryRepository


class PurgeByAuthorUseCase:
    def __init__(self, repo: EntryRepository) -> None:
        self._repo = repo

    async def execute(self, author_id: str, guild_id: str = "") -> int:
        return await self._repo.purge_by_author(author_id, guild_id=guild_id)
```

`lilwman/application/purge_by_tag.py`:
```python
from lilwman.domain.ports import EntryRepository


class PurgeByTagUseCase:
    def __init__(self, repo: EntryRepository) -> None:
        self._repo = repo

    async def execute(self, tag: str, guild_id: str = "") -> int:
        return await self._repo.purge_by_tag(tag, guild_id=guild_id)
```

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/application/test_moderation_use_cases.py -v
```
Expected: all 10 tests pass.

- [ ] **Step 5: Commit**

```bash
git add lilwman/application/get_entry.py \
        lilwman/application/edit_entry.py \
        lilwman/application/list_by_author.py \
        lilwman/application/list_all_entries.py \
        lilwman/application/purge_by_author.py \
        lilwman/application/purge_by_tag.py \
        tests/application/test_moderation_use_cases.py
git commit -m "feat: add moderation use cases (get, edit, list, purge)"
```

---

### Task 6: Config/stats use cases + store_entry guild_id

**Files:**
- Create: `lilwman/application/get_stats.py`
- Create: `lilwman/application/get_guild_config.py`
- Create: `lilwman/application/set_guild_config.py`
- Modify: `lilwman/application/store_entry.py`
- Test: `tests/application/test_stats_config_use_cases.py`

**Interfaces:**
- Consumes: `EntryRepository.get_stats`; `FeedRepository.count_for_guild`; `GuildConfigRepository`
- Produces:
  - `GetStatsUseCase(entry_repo, feed_repo).execute(guild_id) -> BotStats`
  - `GetGuildConfigUseCase(config_repo).execute(guild_id) -> GuildConfig`
  - `SetGuildConfigUseCase(config_repo).execute(guild_id, store_restricted) -> GuildConfig`
  - `StoreEntryUseCase(repo).execute(content, tags, author_id, author_name, guild_id="") -> Entry`

- [ ] **Step 1: Write failing tests**

```python
# tests/application/test_stats_config_use_cases.py
import pytest
from lilwman.application.get_stats import GetStatsUseCase
from lilwman.application.get_guild_config import GetGuildConfigUseCase
from lilwman.application.set_guild_config import SetGuildConfigUseCase
from lilwman.application.store_entry import StoreEntryUseCase


async def test_get_stats_returns_bot_stats(repo, feed_repo):
    await repo.save("entry1", ["python"], "u1", "Alice", guild_id="g1")
    await repo.save("entry2", ["python", "discord"], "u2", "Bob", guild_id="g1")
    stats = await GetStatsUseCase(repo, feed_repo).execute("g1")
    assert stats.total_entries == 2
    assert stats.unique_tags == 2
    assert stats.total_feeds == 0


async def test_get_guild_config_returns_default(guild_config_repo):
    config = await GetGuildConfigUseCase(guild_config_repo).execute("new_guild")
    assert config.store_restricted is False
    assert config.guild_id == "new_guild"


async def test_set_guild_config_persists(guild_config_repo):
    await SetGuildConfigUseCase(guild_config_repo).execute("g1", store_restricted=True)
    config = await GetGuildConfigUseCase(guild_config_repo).execute("g1")
    assert config.store_restricted is True


async def test_store_entry_accepts_guild_id(repo):
    entry = await StoreEntryUseCase(repo).execute(
        content="test", tags=["a"], author_id="u1", author_name="Alice", guild_id="g1"
    )
    assert entry.guild_id == "g1"
```

- [ ] **Step 2: Run to verify fail**

```bash
uv run pytest tests/application/test_stats_config_use_cases.py -v
```
Expected: `ModuleNotFoundError` — missing modules.

- [ ] **Step 3: Create `lilwman/application/get_stats.py`**

```python
from lilwman.domain.admin_entities import BotStats
from lilwman.domain.ports import EntryRepository
from lilwman.domain.feed_ports import FeedRepository


class GetStatsUseCase:
    def __init__(self, entry_repo: EntryRepository, feed_repo: FeedRepository) -> None:
        self._entry_repo = entry_repo
        self._feed_repo = feed_repo

    async def execute(self, guild_id: str) -> BotStats:
        counts = await self._entry_repo.get_stats(guild_id)
        total_feeds = await self._feed_repo.count_for_guild(guild_id)
        return BotStats(
            total_entries=counts["total_entries"],
            entries_this_week=counts["entries_this_week"],
            entries_this_month=counts["entries_this_month"],
            total_feeds=total_feeds,
            unique_tags=counts["unique_tags"],
            top_tags=counts["top_tags"],
            top_authors=counts["top_authors"],
        )
```

- [ ] **Step 4: Create `lilwman/application/get_guild_config.py`**

```python
from lilwman.domain.admin_entities import GuildConfig
from lilwman.domain.admin_ports import GuildConfigRepository


class GetGuildConfigUseCase:
    def __init__(self, config_repo: GuildConfigRepository) -> None:
        self._repo = config_repo

    async def execute(self, guild_id: str) -> GuildConfig:
        return await self._repo.get(guild_id)
```

- [ ] **Step 5: Create `lilwman/application/set_guild_config.py`**

```python
from lilwman.domain.admin_entities import GuildConfig
from lilwman.domain.admin_ports import GuildConfigRepository


class SetGuildConfigUseCase:
    def __init__(self, config_repo: GuildConfigRepository) -> None:
        self._repo = config_repo

    async def execute(self, guild_id: str, store_restricted: bool) -> GuildConfig:
        return await self._repo.save(guild_id, store_restricted)
```

- [ ] **Step 6: Update `lilwman/application/store_entry.py`** — add `guild_id` param

```python
from lilwman.domain.entities import Entry
from lilwman.domain.ports import EntryRepository


class StoreEntryUseCase:
    def __init__(self, repo: EntryRepository) -> None:
        self._repo = repo

    async def execute(
        self,
        content: str,
        tags: list[str],
        author_id: str,
        author_name: str,
        guild_id: str = "",
    ) -> Entry:
        return await self._repo.save(content, tags, author_id, author_name, guild_id=guild_id)
```

- [ ] **Step 7: Run tests**

```bash
uv run pytest tests/application/test_stats_config_use_cases.py -v
```
Expected: all 4 tests pass.

- [ ] **Step 8: Commit**

```bash
git add lilwman/application/get_stats.py \
        lilwman/application/get_guild_config.py \
        lilwman/application/set_guild_config.py \
        lilwman/application/store_entry.py \
        tests/application/test_stats_config_use_cases.py
git commit -m "feat: add stats/config use cases, thread guild_id through store_entry"
```

---

### Task 7: Discord /admin commands + ConfirmView + StoreCog restriction

**Files:**
- Create: `lilwman/bot/admin_views.py`
- Create: `lilwman/bot/commands/admin.py`
- Modify: `lilwman/bot/commands/store.py`
- Test: `tests/bot/test_admin_commands.py`
- Test: `tests/bot/test_admin_views.py`

**Interfaces:**
- Consumes: `GetStatsUseCase`, `EditEntryUseCase`, `ListByAuthorUseCase`, `PurgeByAuthorUseCase`, `PurgeByTagUseCase`, `GetGuildConfigUseCase`, `SetGuildConfigUseCase` (Task 5+6)
- Produces: `AdminCog` with `/admin stats|list-user|edit|purge user|purge tag|config show|config set`; `ConfirmView`; `StoreCog` with `store_restricted` check; bot attributes `get_stats`, `edit_entry`, `list_by_author`, `purge_by_author`, `purge_by_tag`, `get_guild_config`, `set_guild_config`

- [ ] **Step 1: Write failing tests for ConfirmView**

```python
# tests/bot/test_admin_views.py
from unittest.mock import AsyncMock, MagicMock
import discord
from lilwman.bot.admin_views import ConfirmView


async def test_confirm_button_calls_callback():
    callback = AsyncMock(return_value=5)
    view = ConfirmView(callback)

    interaction = AsyncMock(spec=discord.Interaction)
    interaction.response = AsyncMock()

    await view.confirm.callback(view, interaction)

    callback.assert_called_once()
    interaction.response.edit_message.assert_called_once()


async def test_on_timeout_disables_button():
    view = ConfirmView(AsyncMock())
    await view.on_timeout()
    assert view.confirm.disabled is True
```

- [ ] **Step 2: Write failing tests for AdminCog**

```python
# tests/bot/test_admin_commands.py
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime, timezone
import discord
from lilwman.bot.commands.admin import AdminCog
from lilwman.domain.admin_entities import BotStats, GuildConfig
from lilwman.domain.entities import Entry


def _make_bot(**kwargs):
    bot = MagicMock()
    bot.get_stats = kwargs.get("get_stats", AsyncMock())
    bot.edit_entry = kwargs.get("edit_entry", AsyncMock())
    bot.list_by_author = kwargs.get("list_by_author", AsyncMock())
    bot.purge_by_author = kwargs.get("purge_by_author", AsyncMock())
    bot.purge_by_tag = kwargs.get("purge_by_tag", AsyncMock())
    bot.get_guild_config = kwargs.get("get_guild_config", AsyncMock())
    bot.set_guild_config = kwargs.get("set_guild_config", AsyncMock())
    return bot


def _make_interaction(is_admin=True, guild_id=111):
    interaction = AsyncMock(spec=discord.Interaction)
    interaction.user = MagicMock()
    interaction.user.guild_permissions = MagicMock()
    interaction.user.guild_permissions.administrator = is_admin
    interaction.guild_id = guild_id
    interaction.response = AsyncMock()
    return interaction


def _make_entry(id=1):
    now = datetime.now(timezone.utc)
    return Entry(id=id, content="test", tags=["a"], author_id="u1",
                 author_name="Alice", created_at=now, updated_at=now)


async def test_admin_stats_returns_embed(monkeypatch):
    now = datetime.now(timezone.utc)
    stats = BotStats(total_entries=5, entries_this_week=2, entries_this_month=4,
                     total_feeds=1, unique_tags=3, top_tags=[("py", 2)], top_authors=[("Alice", 5)])
    get_stats = AsyncMock()
    get_stats.execute = AsyncMock(return_value=stats)
    cog = AdminCog(_make_bot(get_stats=get_stats))
    interaction = _make_interaction()

    await cog.admin_stats.callback(cog, interaction)

    interaction.response.send_message.assert_called_once()
    call_kwargs = interaction.response.send_message.call_args
    assert call_kwargs.kwargs.get("ephemeral") is True


async def test_admin_non_admin_denied():
    cog = AdminCog(_make_bot())
    interaction = _make_interaction(is_admin=False)
    await cog.admin_stats.callback(cog, interaction)
    call_str = str(interaction.response.send_message.call_args).lower()
    assert "administrator" in call_str or "permission" in call_str


async def test_admin_dm_denied():
    cog = AdminCog(_make_bot())
    interaction = _make_interaction(guild_id=None)
    await cog.admin_stats.callback(cog, interaction)
    call_str = str(interaction.response.send_message.call_args).lower()
    assert "server" in call_str or "guild" in call_str


async def test_admin_edit_calls_use_case():
    edit_uc = AsyncMock()
    edit_uc.execute = AsyncMock(return_value=_make_entry())
    cog = AdminCog(_make_bot(edit_entry=edit_uc))
    interaction = _make_interaction()

    await cog.admin_edit.callback(cog, interaction, id=1, content="new content", tags="a, b")

    edit_uc.execute.assert_called_once_with(1, "new content", ["a", "b"])
    interaction.response.send_message.assert_called_once()


async def test_admin_purge_user_shows_confirmation():
    purge_uc = AsyncMock()
    purge_uc.execute = AsyncMock(return_value=3)
    list_uc = AsyncMock()
    list_uc.execute = AsyncMock(return_value=[_make_entry(), _make_entry(2), _make_entry(3)])
    cog = AdminCog(_make_bot(purge_by_author=purge_uc, list_by_author=list_uc))
    interaction = _make_interaction()
    user = MagicMock(spec=discord.Member)
    user.id = 999

    await cog.purge_user.callback(cog, interaction, user=user)

    interaction.response.send_message.assert_called_once()
    call_kwargs = interaction.response.send_message.call_args
    assert call_kwargs.kwargs.get("ephemeral") is True
    assert "view" in call_kwargs.kwargs


async def test_admin_config_show_returns_embed():
    now = datetime.now(timezone.utc)
    config = GuildConfig(guild_id="111", store_restricted=False, created_at=now, updated_at=now)
    get_cfg = AsyncMock()
    get_cfg.execute = AsyncMock(return_value=config)
    cog = AdminCog(_make_bot(get_guild_config=get_cfg))
    interaction = _make_interaction()

    await cog.config_show.callback(cog, interaction)

    interaction.response.send_message.assert_called_once()
    assert interaction.response.send_message.call_args.kwargs.get("ephemeral") is True


async def test_store_restricted_blocks_non_admin(monkeypatch):
    from lilwman.bot.commands.store import StoreCog
    now = datetime.now(timezone.utc)
    config = GuildConfig(guild_id="111", store_restricted=True, created_at=now, updated_at=now)
    get_cfg = AsyncMock()
    get_cfg.execute = AsyncMock(return_value=config)

    bot = MagicMock()
    bot.store_entry = AsyncMock()
    bot.get_guild_config = get_cfg
    cog = StoreCog(bot)

    interaction = AsyncMock(spec=discord.Interaction)
    interaction.user = MagicMock()
    interaction.user.guild_permissions = MagicMock()
    interaction.user.guild_permissions.administrator = False
    interaction.guild_id = 111
    interaction.response = AsyncMock()

    await cog.store.callback(cog, interaction, content="test", tags="")

    bot.store_entry.execute.assert_not_called()
    call_str = str(interaction.response.send_message.call_args).lower()
    assert "restricted" in call_str or "admin" in call_str
```

- [ ] **Step 3: Run to verify fail**

```bash
uv run pytest tests/bot/test_admin_views.py tests/bot/test_admin_commands.py -v
```
Expected: `ModuleNotFoundError`.

- [ ] **Step 4: Create `lilwman/bot/admin_views.py`**

```python
from typing import Callable, Awaitable

import discord


class ConfirmView(discord.ui.View):
    def __init__(self, callback: Callable[[], Awaitable[int]], timeout: float = 60.0) -> None:
        super().__init__(timeout=timeout)
        self._callback = callback

    @discord.ui.button(label="Confirm", style=discord.ButtonStyle.danger)
    async def confirm(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        count = await self._callback()
        button.disabled = True
        self.stop()
        await interaction.response.edit_message(
            content=f"Done. Deleted **{count}** entries.", view=self
        )

    async def on_timeout(self) -> None:
        self.confirm.disabled = True
        self.stop()
```

- [ ] **Step 5: Create `lilwman/bot/commands/admin.py`**

```python
import discord
from discord import app_commands
from discord.ext import commands

from lilwman.bot.admin_views import ConfirmView


def _admin_guard(interaction: discord.Interaction) -> bool:
    if interaction.guild_id is None:
        return False
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
        if not getattr(getattr(interaction.user, "guild_permissions", None), "administrator", False):
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
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @admin.command(name="list-user", description="List entries by a user")
    @app_commands.describe(user="Discord member")
    async def admin_list_user(self, interaction: discord.Interaction, user: discord.Member) -> None:
        if interaction.guild_id is None:
            await interaction.response.send_message(
                "Admin commands can only be used in a server.", ephemeral=True
            )
            return
        if not getattr(getattr(interaction.user, "guild_permissions", None), "administrator", False):
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
        if not getattr(getattr(interaction.user, "guild_permissions", None), "administrator", False):
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
        if not getattr(getattr(interaction.user, "guild_permissions", None), "administrator", False):
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
        if not getattr(getattr(interaction.user, "guild_permissions", None), "administrator", False):
            await interaction.response.send_message(
                "Administrator permission required.", ephemeral=True
            )
            return
        from lilwman.application.search_entries import SearchEntriesUseCase
        tagged = await self.bot.list_all_entries.execute()
        tagged_entries = [e for e in tagged[0] if tag.lower() in [t.lower() for t in e.tags]]
        count = len(tagged_entries)

        async def do_purge() -> int:
            return await self.bot.purge_by_tag.execute(tag)

        if count == 0:
            await interaction.response.send_message(
                f"No entries found with tag **{tag}**.", ephemeral=True
            )
            return
        view = ConfirmView(do_purge)
        await interaction.response.send_message(
            f"This will delete entries tagged **{tag}** (~{count} entries). Confirm?",
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
        if not getattr(getattr(interaction.user, "guild_permissions", None), "administrator", False):
            await interaction.response.send_message(
                "Administrator permission required.", ephemeral=True
            )
            return
        config = await self.bot.get_guild_config.execute(str(interaction.guild_id))
        embed = discord.Embed(title="Guild Configuration", color=0x5865F2)
        embed.add_field(
            name="store_restricted",
            value="✅ Enabled (only admins can /store)" if config.store_restricted else "❌ Disabled (anyone can /store)",
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
        if not getattr(getattr(interaction.user, "guild_permissions", None), "administrator", False):
            await interaction.response.send_message(
                "Administrator permission required.", ephemeral=True
            )
            return
        await self.bot.set_guild_config.execute(str(interaction.guild_id), store_restricted)
        state = "enabled" if store_restricted else "disabled"
        await interaction.response.send_message(
            f"store_restricted {state}.", ephemeral=True
        )
```

- [ ] **Step 6: Update `lilwman/bot/commands/store.py`** — check `store_restricted` and pass `guild_id`

```python
import discord
from discord import app_commands
from discord.ext import commands


class StoreCog(commands.Cog):
    def __init__(self, bot) -> None:
        self.bot = bot

    @app_commands.command(name="store", description="Store a wiki entry")
    @app_commands.describe(
        content="The content to store",
        tags="Comma-separated tags (optional)",
    )
    async def store(
        self,
        interaction: discord.Interaction,
        content: str,
        tags: str = "",
    ) -> None:
        guild_id = str(interaction.guild_id) if interaction.guild_id else ""
        is_admin = getattr(
            getattr(interaction.user, "guild_permissions", None), "administrator", False
        )
        if guild_id and not is_admin:
            config = await self.bot.get_guild_config.execute(guild_id)
            if config.store_restricted:
                await interaction.response.send_message(
                    "Storing entries is restricted to admins on this server.",
                    ephemeral=True,
                )
                return
        tag_list = [t.strip() for t in tags.split(",") if t.strip()]
        entry = await self.bot.store_entry.execute(
            content=content,
            tags=tag_list,
            author_id=str(interaction.user.id),
            author_name=interaction.user.display_name,
            guild_id=guild_id,
        )
        tag_display = f" [{', '.join(entry.tags)}]" if entry.tags else ""
        await interaction.response.send_message(
            f"Stored entry **#{entry.id}**{tag_display}."
        )
```

- [ ] **Step 7: Run tests**

```bash
uv run pytest tests/bot/test_admin_views.py tests/bot/test_admin_commands.py -v
```
Expected: all tests pass.

- [ ] **Step 8: Full test suite**

```bash
uv run pytest -q
```
Expected: all existing tests pass (StoreCog tests may need updating if they call `store_entry.execute` without `get_guild_config` on bot — add `bot.get_guild_config = AsyncMock()` with a default GuildConfig return to any failing store tests).

- [ ] **Step 9: Commit**

```bash
git add lilwman/bot/admin_views.py \
        lilwman/bot/commands/admin.py \
        lilwman/bot/commands/store.py \
        tests/bot/test_admin_views.py \
        tests/bot/test_admin_commands.py
git commit -m "feat: add AdminCog, ConfirmView, store_restricted check in StoreCog"
```

---

### Task 8: FastAPI app + Discord OAuth auth

**Files:**
- Create: `lilwman/infrastructure/web/__init__.py`
- Create: `lilwman/infrastructure/web/app.py`
- Create: `lilwman/infrastructure/web/auth.py`
- Create: `lilwman/infrastructure/web/routes/__init__.py`
- Create: `lilwman/infrastructure/web/templates/base.html`
- Create: `lilwman/infrastructure/web/templates/login.html`
- Modify: `pyproject.toml`
- Test: `tests/infrastructure/test_web_auth.py`

**Interfaces:**
- Produces: `create_app(**kwargs) -> FastAPI`; `require_login` dependency; `LoginRequired` exception; `get_flash(request)`; `redirect_with_flash(url, message)`; auth routes `GET /login`, `GET /auth/discord`, `GET /auth/callback`

- [ ] **Step 1: Add dependencies to `pyproject.toml`**

```toml
dependencies = [
    "discord.py>=2.4",
    "sqlalchemy[asyncio]>=2.0",
    "aiosqlite>=0.20",
    "alembic>=1.13",
    "pydantic-settings>=2.7",
    "ollama>=0.3",
    "aiohttp>=3.9",
    "feedparser>=6.0",
    "fastapi>=0.115",
    "uvicorn>=0.30",
    "jinja2>=3.1",
    "itsdangerous>=2.1",
    "httpx>=0.27",
]
```

Then install:
```bash
uv sync
```

- [ ] **Step 2: Write failing auth tests**

```python
# tests/infrastructure/test_web_auth.py
from unittest.mock import AsyncMock, patch, MagicMock
import pytest
from itsdangerous import URLSafeTimedSerializer
from lilwman.infrastructure.web.auth import (
    make_serializer, get_session_data, build_oauth_url,
)


def test_build_oauth_url_contains_client_id():
    url = build_oauth_url("12345", "http://localhost:8080/auth/callback")
    assert "12345" in url
    assert "discord.com/oauth2/authorize" in url
    assert "identify" in url


def test_session_roundtrip():
    s = make_serializer("test-secret-key")
    data = {"user_id": "123", "username": "alice", "avatar": ""}

    from itsdangerous import URLSafeTimedSerializer
    cookie = s.dumps(data)
    result = get_session_data(cookie, s)
    assert result is not None
    assert result["user_id"] == "123"


def test_get_session_data_invalid_returns_none():
    s = make_serializer("test-secret-key")
    result = get_session_data("not-a-valid-cookie", s)
    assert result is None


def test_get_session_data_missing_returns_none():
    s = make_serializer("test-secret-key")
    result = get_session_data(None, s)
    assert result is None
```

- [ ] **Step 3: Run to verify fail**

```bash
uv run pytest tests/infrastructure/test_web_auth.py -v
```
Expected: `ModuleNotFoundError`.

- [ ] **Step 4: Create `lilwman/infrastructure/web/__init__.py`** — empty

```python
```

- [ ] **Step 5: Create `lilwman/infrastructure/web/routes/__init__.py`** — empty

```python
```

- [ ] **Step 6: Create `lilwman/infrastructure/web/auth.py`**

```python
from urllib.parse import urlencode

import aiohttp
from fastapi import APIRouter, Request, Response
from fastapi.responses import RedirectResponse
from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadSignature

router = APIRouter()


class LoginRequired(Exception):
    def __init__(self, redirect_to: str = "/login") -> None:
        self.redirect_to = redirect_to


def make_serializer(secret_key: str) -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(secret_key)


def get_session_data(cookie: str | None, serializer: URLSafeTimedSerializer) -> dict | None:
    if not cookie:
        return None
    try:
        return serializer.loads(cookie, max_age=86400)
    except (SignatureExpired, BadSignature):
        return None


def build_oauth_url(client_id: str, redirect_uri: str) -> str:
    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": "identify guilds",
    }
    return f"https://discord.com/oauth2/authorize?{urlencode(params)}"


def require_login(request: Request) -> dict:
    serializer = URLSafeTimedSerializer(request.app.state.secret_key)
    cookie = request.cookies.get("session")
    data = get_session_data(cookie, serializer)
    if data is None:
        if cookie:
            raise LoginRequired("/login?error=session_expired")
        raise LoginRequired("/login")
    return data


def get_flash(request: Request) -> str | None:
    return request.cookies.get("flash")


def redirect_with_flash(url: str, message: str) -> RedirectResponse:
    response = RedirectResponse(url, status_code=303)
    response.set_cookie("flash", message, max_age=10, httponly=True, samesite="lax")
    return response


@router.get("/login")
async def login_page(request: Request, error: str = ""):
    templates = request.app.state.templates
    return templates.TemplateResponse(
        "login.html", {"request": request, "error": error}
    )


@router.get("/auth/discord")
async def discord_oauth_redirect(request: Request) -> RedirectResponse:
    redirect_uri = f"{request.app.state.web_base_url}/auth/callback"
    url = build_oauth_url(request.app.state.client_id, redirect_uri)
    return RedirectResponse(url)


@router.get("/auth/callback")
async def discord_oauth_callback(request: Request, code: str = "") -> Response:
    if not code:
        return RedirectResponse("/login?error=auth_failed")

    redirect_uri = f"{request.app.state.web_base_url}/auth/callback"
    token_data = {
        "client_id": request.app.state.client_id,
        "client_secret": request.app.state.client_secret,
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": redirect_uri,
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(
            "https://discord.com/api/oauth2/token", data=token_data
        ) as resp:
            if resp.status != 200:
                return RedirectResponse("/login?error=auth_failed")
            token_json = await resp.json()

        access_token = token_json.get("access_token")
        if not access_token:
            return RedirectResponse("/login?error=auth_failed")

        headers = {"Authorization": f"Bearer {access_token}"}

        async with session.get("https://discord.com/api/users/@me", headers=headers) as resp:
            if resp.status != 200:
                return RedirectResponse("/login?error=auth_failed")
            user_data = await resp.json()

        async with session.get("https://discord.com/api/users/@me/guilds", headers=headers) as resp:
            if resp.status != 200:
                return RedirectResponse("/login?error=auth_failed")
            guilds = await resp.json()

    bot_guild_id = request.app.state.web_guild_id
    ADMINISTRATOR = 0x8
    authorized = any(
        str(g["id"]) == str(bot_guild_id) and (int(g.get("permissions", 0)) & ADMINISTRATOR)
        for g in guilds
    )
    if not authorized:
        return RedirectResponse("/login?error=not_authorized")

    session_data = {
        "user_id": str(user_data["id"]),
        "username": user_data["username"],
        "avatar": user_data.get("avatar") or "",
    }
    serializer = URLSafeTimedSerializer(request.app.state.secret_key)
    cookie_value = serializer.dumps(session_data)

    response = RedirectResponse("/", status_code=303)
    response.set_cookie("session", cookie_value, httponly=True, samesite="lax", max_age=86400)
    return response


@router.get("/logout")
async def logout() -> RedirectResponse:
    response = RedirectResponse("/login", status_code=303)
    response.delete_cookie("session")
    return response
```

- [ ] **Step 7: Create `lilwman/infrastructure/web/app.py`**

```python
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from .auth import LoginRequired, router as auth_router


def create_app(
    *,
    secret_key: str,
    client_id: str,
    client_secret: str,
    web_base_url: str,
    web_guild_id: str,
    get_stats,
    get_entry,
    edit_entry,
    list_all_entries,
    list_by_author,
    purge_by_author,
    purge_by_tag,
    delete_entry,
    list_all_feeds,
    delete_feed,
    get_guild_config,
    set_guild_config,
) -> FastAPI:
    app = FastAPI(docs_url=None, redoc_url=None)

    app.state.secret_key = secret_key
    app.state.client_id = client_id
    app.state.client_secret = client_secret
    app.state.web_base_url = web_base_url
    app.state.web_guild_id = web_guild_id
    app.state.get_stats = get_stats
    app.state.get_entry = get_entry
    app.state.edit_entry = edit_entry
    app.state.list_all_entries = list_all_entries
    app.state.list_by_author = list_by_author
    app.state.purge_by_author = purge_by_author
    app.state.purge_by_tag = purge_by_tag
    app.state.delete_entry = delete_entry
    app.state.list_all_feeds = list_all_feeds
    app.state.delete_feed = delete_feed
    app.state.get_guild_config = get_guild_config
    app.state.set_guild_config = set_guild_config

    templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))
    app.state.templates = templates

    @app.exception_handler(LoginRequired)
    async def login_required_handler(request: Request, exc: LoginRequired):
        return RedirectResponse(exc.redirect_to)

    app.include_router(auth_router)

    from .routes.dashboard import router as dashboard_router
    from .routes.entries import router as entries_router
    from .routes.feeds import router as feeds_router
    from .routes.config_route import router as config_router

    app.include_router(dashboard_router)
    app.include_router(entries_router)
    app.include_router(feeds_router)
    app.include_router(config_router)

    return app
```

- [ ] **Step 8: Create `lilwman/infrastructure/web/templates/login.html`**

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>lilwman — Login</title>
  <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-gray-100 min-h-screen flex items-center justify-center">
  <div class="bg-white rounded-lg shadow p-8 w-80 text-center">
    <h1 class="text-2xl font-bold mb-2">lilwman admin</h1>
    <p class="text-gray-500 mb-6">Sign in with Discord to continue</p>
    {% if error %}
    <div class="mb-4 bg-red-100 text-red-800 px-4 py-2 rounded text-sm">
      {% if error == "auth_failed" %}Authentication failed. Please try again.
      {% elif error == "not_authorized" %}You are not an administrator in the connected server.
      {% elif error == "session_expired" %}Your session expired. Please sign in again.
      {% else %}An error occurred. Please try again.{% endif %}
    </div>
    {% endif %}
    <a href="/auth/discord"
       class="block bg-indigo-600 text-white py-2 px-4 rounded hover:bg-indigo-700 transition">
      Login with Discord
    </a>
  </div>
</body>
</html>
```

- [ ] **Step 9: Create `lilwman/infrastructure/web/templates/base.html`**

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>lilwman admin{% block title %}{% endblock %}</title>
  <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-gray-100 min-h-screen flex">
  <aside class="w-56 bg-gray-900 text-white flex flex-col py-6 px-4 min-h-screen shrink-0">
    <h1 class="text-xl font-bold mb-8">lilwman</h1>
    <nav class="flex flex-col gap-1">
      <a href="/" class="hover:bg-gray-700 px-3 py-2 rounded text-sm">📊 Dashboard</a>
      <a href="/entries" class="hover:bg-gray-700 px-3 py-2 rounded text-sm">📝 Entries</a>
      <a href="/feeds" class="hover:bg-gray-700 px-3 py-2 rounded text-sm">📡 Feeds</a>
      <a href="/config" class="hover:bg-gray-700 px-3 py-2 rounded text-sm">⚙️ Config</a>
    </nav>
    <div class="mt-auto">
      <div class="text-xs text-gray-400 mb-1">{{ user.username }}</div>
      <a href="/logout" class="text-xs text-gray-500 hover:text-white">Logout</a>
    </div>
  </aside>
  <main class="flex-1 p-8 overflow-auto">
    {% if flash %}
    <div class="mb-4 bg-green-100 border border-green-300 text-green-800 px-4 py-3 rounded text-sm">
      {{ flash }}
    </div>
    {% endif %}
    {% block content %}{% endblock %}
  </main>
</body>
</html>
```

- [ ] **Step 10: Run auth tests**

```bash
uv run pytest tests/infrastructure/test_web_auth.py -v
```
Expected: 4 tests pass.

- [ ] **Step 11: Commit**

```bash
git add lilwman/infrastructure/web/__init__.py \
        lilwman/infrastructure/web/app.py \
        lilwman/infrastructure/web/auth.py \
        lilwman/infrastructure/web/routes/__init__.py \
        lilwman/infrastructure/web/templates/base.html \
        lilwman/infrastructure/web/templates/login.html \
        tests/infrastructure/test_web_auth.py \
        pyproject.toml
git commit -m "feat: add FastAPI web app factory, Discord OAuth auth, base templates"
```

---

### Task 9: Web routes and templates

**Files:**
- Create: `lilwman/infrastructure/web/routes/dashboard.py`
- Create: `lilwman/infrastructure/web/routes/entries.py`
- Create: `lilwman/infrastructure/web/routes/feeds.py`
- Create: `lilwman/infrastructure/web/routes/config_route.py`
- Create: `lilwman/infrastructure/web/templates/dashboard.html`
- Create: `lilwman/infrastructure/web/templates/entries.html`
- Create: `lilwman/infrastructure/web/templates/entry_edit.html`
- Create: `lilwman/infrastructure/web/templates/feeds.html`
- Create: `lilwman/infrastructure/web/templates/config.html`
- Test: `tests/infrastructure/test_web_routes.py`

**Interfaces:**
- Consumes: `create_app` from Task 8; all use cases via `request.app.state.*`; `require_login`, `get_flash`, `redirect_with_flash` from `auth.py`
- Produces: all web pages for dashboard, entries browser, feeds list, guild config

- [ ] **Step 1: Write failing route tests**

```python
# tests/infrastructure/test_web_routes.py
import pytest
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime, timezone
from httpx import AsyncClient, ASGITransport

from lilwman.infrastructure.web.app import create_app
from lilwman.infrastructure.web.auth import require_login
from lilwman.domain.admin_entities import BotStats, GuildConfig
from lilwman.domain.entities import Entry
from lilwman.domain.feed_entities import FeedSubscription


def _entry(id=1, content="test", tags=None, author="Alice", author_id="u1"):
    now = datetime.now(timezone.utc)
    return Entry(id=id, content=content, tags=tags or [], author_id=author_id,
                 author_name=author, created_at=now, updated_at=now)


def _feed(id=1):
    now = datetime.now(timezone.utc)
    return FeedSubscription(id=id, channel_id="ch1", platform="reddit",
                            account_name="python", rss_url="http://x.com", created_at=now)


def _make_app(**overrides):
    now = datetime.now(timezone.utc)
    defaults = dict(
        secret_key="test-secret",
        client_id="cid",
        client_secret="csec",
        web_base_url="http://localhost:8080",
        web_guild_id="123",
        get_stats=MagicMock(execute=AsyncMock(return_value=BotStats(
            total_entries=5, entries_this_week=1, entries_this_month=3,
            total_feeds=2, unique_tags=4, top_tags=[("py", 3)], top_authors=[("Alice", 5)]
        ))),
        get_entry=MagicMock(execute=AsyncMock(return_value=_entry())),
        edit_entry=MagicMock(execute=AsyncMock(return_value=_entry())),
        list_all_entries=MagicMock(execute=AsyncMock(return_value=([_entry()], 1))),
        list_by_author=MagicMock(execute=AsyncMock(return_value=[_entry()])),
        purge_by_author=MagicMock(execute=AsyncMock(return_value=2)),
        purge_by_tag=MagicMock(execute=AsyncMock(return_value=3)),
        delete_entry=MagicMock(execute=AsyncMock(return_value=True)),
        list_all_feeds=MagicMock(execute=AsyncMock(return_value=[_feed()])),
        delete_feed=MagicMock(execute=AsyncMock(return_value=True)),
        get_guild_config=MagicMock(execute=AsyncMock(return_value=GuildConfig(
            guild_id="123", store_restricted=False, created_at=now, updated_at=now
        ))),
        set_guild_config=MagicMock(execute=AsyncMock(return_value=GuildConfig(
            guild_id="123", store_restricted=True, created_at=now, updated_at=now
        ))),
    )
    defaults.update(overrides)
    app = create_app(**defaults)
    app.dependency_overrides[require_login] = lambda: {
        "user_id": "1", "username": "testadmin", "avatar": ""
    }
    return app


@pytest.fixture
async def client():
    app = _make_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


async def test_dashboard_returns_200(client):
    resp = await client.get("/")
    assert resp.status_code == 200
    assert "Dashboard" in resp.text


async def test_entries_page_returns_200(client):
    resp = await client.get("/entries")
    assert resp.status_code == 200
    assert "Entries" in resp.text


async def test_entry_edit_page_returns_200(client):
    resp = await client.get("/entries/1/edit")
    assert resp.status_code == 200
    assert "Edit Entry" in resp.text


async def test_entry_edit_post_redirects(client):
    resp = await client.post("/entries/1/edit", data={"content": "new", "tags": "a,b"},
                             follow_redirects=False)
    assert resp.status_code == 303
    assert "/entries" in resp.headers["location"]


async def test_entry_delete_redirects(client):
    resp = await client.post("/entries/1/delete", follow_redirects=False)
    assert resp.status_code == 303


async def test_purge_user_redirects(client):
    resp = await client.post("/entries/purge/user", data={"author_id": "u1"},
                             follow_redirects=False)
    assert resp.status_code == 303


async def test_purge_tag_redirects(client):
    resp = await client.post("/entries/purge/tag", data={"tag": "spam"},
                             follow_redirects=False)
    assert resp.status_code == 303


async def test_feeds_page_returns_200(client):
    resp = await client.get("/feeds")
    assert resp.status_code == 200
    assert "Feed" in resp.text


async def test_feed_delete_redirects(client):
    resp = await client.post("/feeds/1/delete", follow_redirects=False)
    assert resp.status_code == 303


async def test_config_page_returns_200(client):
    resp = await client.get("/config")
    assert resp.status_code == 200
    assert "Config" in resp.text


async def test_config_post_redirects(client):
    resp = await client.post("/config", data={"store_restricted": "true"},
                             follow_redirects=False)
    assert resp.status_code == 303


async def test_unauthenticated_redirects_to_login():
    app = _make_app()
    app.dependency_overrides = {}  # remove login override
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.get("/", follow_redirects=False)
    assert resp.status_code in (302, 303, 307)
```

- [ ] **Step 2: Run to verify fail**

```bash
uv run pytest tests/infrastructure/test_web_routes.py -v
```
Expected: `ImportError` — route modules missing.

- [ ] **Step 3: Create `lilwman/infrastructure/web/routes/dashboard.py`**

```python
from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse

from ..auth import require_login, get_flash

router = APIRouter()


@router.get("/", response_class=HTMLResponse)
async def dashboard(request: Request, user: dict = Depends(require_login)) -> HTMLResponse:
    flash = get_flash(request)
    stats = await request.app.state.get_stats.execute(request.app.state.web_guild_id)
    response = request.app.state.templates.TemplateResponse(
        "dashboard.html", {"request": request, "stats": stats, "user": user, "flash": flash}
    )
    response.delete_cookie("flash")
    return response
```

- [ ] **Step 4: Create `lilwman/infrastructure/web/routes/entries.py`**

```python
from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from ..auth import require_login, get_flash, redirect_with_flash

router = APIRouter(prefix="/entries")


@router.get("", response_class=HTMLResponse)
async def entries_list(
    request: Request,
    user: dict = Depends(require_login),
    q: str = "",
    author_id: str = "",
    page: int = 1,
) -> HTMLResponse:
    flash = get_flash(request)
    per_page = 20
    if q:
        entries = await request.app.state.list_all_entries.execute()
        all_entries, _ = entries
        from lilwman.application.search_entries import SearchEntriesUseCase
        all_entries = await request.app.state.list_all_entries.execute(page=1, per_page=9999)
        entries_list_data = [
            e for e in all_entries[0]
            if q.lower() in e.content.lower() or any(q.lower() in t for t in e.tags)
        ]
        total = len(entries_list_data)
        offset = (page - 1) * per_page
        entries_page = entries_list_data[offset:offset + per_page]
    elif author_id:
        entries_page = await request.app.state.list_by_author.execute(author_id)
        total = len(entries_page)
    else:
        entries_page, total = await request.app.state.list_all_entries.execute(page=page, per_page=per_page)

    has_next = (page * per_page) < total
    response = request.app.state.templates.TemplateResponse(
        "entries.html",
        {
            "request": request, "entries": entries_page, "user": user,
            "flash": flash, "q": q, "author_id": author_id,
            "page": page, "has_next": has_next, "total": total,
        },
    )
    response.delete_cookie("flash")
    return response


@router.get("/{entry_id}/edit", response_class=HTMLResponse)
async def entry_edit_form(
    request: Request, entry_id: int, user: dict = Depends(require_login)
) -> HTMLResponse:
    entry = await request.app.state.get_entry.execute(entry_id)
    if entry is None:
        return redirect_with_flash("/entries", f"Entry #{entry_id} not found.")
    flash = get_flash(request)
    response = request.app.state.templates.TemplateResponse(
        "entry_edit.html", {"request": request, "entry": entry, "user": user, "flash": flash}
    )
    response.delete_cookie("flash")
    return response


@router.post("/{entry_id}/edit")
async def entry_edit_save(
    request: Request,
    entry_id: int,
    user: dict = Depends(require_login),
    content: str = Form(...),
    tags: str = Form(""),
) -> RedirectResponse:
    tag_list = [t.strip() for t in tags.split(",") if t.strip()]
    entry = await request.app.state.edit_entry.execute(entry_id, content, tag_list)
    if entry is None:
        return redirect_with_flash("/entries", f"Entry #{entry_id} not found.")
    return redirect_with_flash("/entries", f"Entry #{entry_id} updated.")


@router.post("/{entry_id}/delete")
async def entry_delete(
    request: Request, entry_id: int, user: dict = Depends(require_login)
) -> RedirectResponse:
    await request.app.state.delete_entry.execute(entry_id, "web-admin", is_admin=True)
    return redirect_with_flash("/entries", f"Entry #{entry_id} deleted.")


@router.post("/purge/user")
async def purge_user(
    request: Request,
    user: dict = Depends(require_login),
    author_id: str = Form(...),
) -> RedirectResponse:
    count = await request.app.state.purge_by_author.execute(author_id)
    return redirect_with_flash("/entries", f"Deleted {count} entries.")


@router.post("/purge/tag")
async def purge_tag(
    request: Request,
    user: dict = Depends(require_login),
    tag: str = Form(...),
) -> RedirectResponse:
    count = await request.app.state.purge_by_tag.execute(tag)
    return redirect_with_flash("/entries", f"Deleted {count} entries tagged '{tag}'.")
```

- [ ] **Step 5: Create `lilwman/infrastructure/web/routes/feeds.py`**

```python
from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from ..auth import require_login, get_flash, redirect_with_flash

router = APIRouter(prefix="/feeds")


@router.get("", response_class=HTMLResponse)
async def feeds_list(request: Request, user: dict = Depends(require_login)) -> HTMLResponse:
    flash = get_flash(request)
    feeds = await request.app.state.list_all_feeds.execute()
    response = request.app.state.templates.TemplateResponse(
        "feeds.html", {"request": request, "feeds": feeds, "user": user, "flash": flash}
    )
    response.delete_cookie("flash")
    return response


@router.post("/{feed_id}/delete")
async def feed_delete(
    request: Request, feed_id: int, user: dict = Depends(require_login)
) -> RedirectResponse:
    await request.app.state.delete_feed.execute(feed_id, channel_id="", admin=True)
    return redirect_with_flash("/feeds", f"Feed #{feed_id} deleted.")
```

- [ ] **Step 6: Create `lilwman/infrastructure/web/routes/config_route.py`**

```python
from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from ..auth import require_login, get_flash, redirect_with_flash

router = APIRouter()


@router.get("/config", response_class=HTMLResponse)
async def config_page(request: Request, user: dict = Depends(require_login)) -> HTMLResponse:
    flash = get_flash(request)
    config = await request.app.state.get_guild_config.execute(request.app.state.web_guild_id)
    response = request.app.state.templates.TemplateResponse(
        "config.html", {"request": request, "config": config, "user": user, "flash": flash}
    )
    response.delete_cookie("flash")
    return response


@router.post("/config")
async def config_save(
    request: Request,
    user: dict = Depends(require_login),
    store_restricted: str = Form(""),
) -> RedirectResponse:
    value = store_restricted.lower() in ("true", "on", "1", "yes")
    await request.app.state.set_guild_config.execute(request.app.state.web_guild_id, value)
    return redirect_with_flash("/config", "Configuration saved.")
```

- [ ] **Step 7: Create all 5 remaining templates**

`lilwman/infrastructure/web/templates/dashboard.html`:
```html
{% extends "base.html" %}
{% block title %} — Dashboard{% endblock %}
{% block content %}
<h2 class="text-2xl font-bold mb-6">Dashboard</h2>
<div class="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
  <div class="bg-white rounded-lg shadow p-4">
    <div class="text-3xl font-bold text-indigo-600">{{ stats.total_entries }}</div>
    <div class="text-gray-500 text-sm mt-1">Total entries</div>
  </div>
  <div class="bg-white rounded-lg shadow p-4">
    <div class="text-3xl font-bold text-green-600">{{ stats.entries_this_week }}</div>
    <div class="text-gray-500 text-sm mt-1">This week</div>
  </div>
  <div class="bg-white rounded-lg shadow p-4">
    <div class="text-3xl font-bold text-blue-600">{{ stats.total_feeds }}</div>
    <div class="text-gray-500 text-sm mt-1">Feed subscriptions</div>
  </div>
  <div class="bg-white rounded-lg shadow p-4">
    <div class="text-3xl font-bold text-purple-600">{{ stats.unique_tags }}</div>
    <div class="text-gray-500 text-sm mt-1">Unique tags</div>
  </div>
</div>
<div class="grid grid-cols-1 md:grid-cols-2 gap-6">
  <div class="bg-white rounded-lg shadow p-5">
    <h3 class="font-semibold mb-3 text-gray-700">Top Tags</h3>
    {% for tag, count in stats.top_tags %}
    <div class="flex justify-between items-center py-2 border-b last:border-0">
      <span class="text-sm">{{ tag }}</span>
      <span class="text-sm text-gray-500 font-medium">{{ count }}</span>
    </div>
    {% else %}
    <p class="text-gray-400 text-sm">No tags yet.</p>
    {% endfor %}
  </div>
  <div class="bg-white rounded-lg shadow p-5">
    <h3 class="font-semibold mb-3 text-gray-700">Top Authors</h3>
    {% for author, count in stats.top_authors %}
    <div class="flex justify-between items-center py-2 border-b last:border-0">
      <span class="text-sm">{{ author }}</span>
      <span class="text-sm text-gray-500 font-medium">{{ count }}</span>
    </div>
    {% else %}
    <p class="text-gray-400 text-sm">No entries yet.</p>
    {% endfor %}
  </div>
</div>
{% endblock %}
```

`lilwman/infrastructure/web/templates/entries.html`:
```html
{% extends "base.html" %}
{% block title %} — Entries{% endblock %}
{% block content %}
<div class="flex justify-between items-center mb-4">
  <h2 class="text-2xl font-bold">Entries <span class="text-gray-400 text-lg">({{ total }})</span></h2>
  <form method="get" class="flex gap-2">
    <input name="q" value="{{ q }}" placeholder="Search content/tags…"
           class="border rounded px-3 py-1.5 text-sm w-48">
    <input name="author_id" value="{{ author_id }}" placeholder="Author ID…"
           class="border rounded px-3 py-1.5 text-sm w-36">
    <button type="submit" class="bg-indigo-600 text-white px-4 py-1.5 rounded text-sm">Filter</button>
    {% if q or author_id %}<a href="/entries" class="px-3 py-1.5 border rounded text-sm hover:bg-gray-50">Clear</a>{% endif %}
  </form>
</div>
<div class="mb-4 flex gap-3">
  <form method="post" action="/entries/purge/user" class="flex gap-2">
    <input name="author_id" placeholder="Author ID" class="border rounded px-3 py-1 text-sm w-36">
    <button type="submit" class="bg-red-600 text-white px-3 py-1 rounded text-sm"
            onclick="return confirm('Delete ALL entries for this author?')">Purge user</button>
  </form>
  <form method="post" action="/entries/purge/tag" class="flex gap-2">
    <input name="tag" placeholder="Tag name" class="border rounded px-3 py-1 text-sm w-32">
    <button type="submit" class="bg-red-600 text-white px-3 py-1 rounded text-sm"
            onclick="return confirm('Delete ALL entries with this tag?')">Purge tag</button>
  </form>
</div>
<div class="bg-white rounded-lg shadow overflow-hidden">
  <table class="w-full text-sm">
    <thead class="bg-gray-50 text-gray-600 uppercase text-xs">
      <tr>
        <th class="px-4 py-3 text-left w-12">ID</th>
        <th class="px-4 py-3 text-left">Content</th>
        <th class="px-4 py-3 text-left w-36">Tags</th>
        <th class="px-4 py-3 text-left w-28">Author</th>
        <th class="px-4 py-3 text-left w-24">Date</th>
        <th class="px-4 py-3 text-left w-24">Actions</th>
      </tr>
    </thead>
    <tbody>
      {% for entry in entries %}
      <tr class="border-t hover:bg-gray-50">
        <td class="px-4 py-2 text-gray-400">#{{ entry.id }}</td>
        <td class="px-4 py-2">{{ entry.content[:120] }}{% if entry.content|length > 120 %}…{% endif %}</td>
        <td class="px-4 py-2 text-gray-500">{{ entry.tags | join(', ') }}</td>
        <td class="px-4 py-2">{{ entry.author_name }}</td>
        <td class="px-4 py-2 text-gray-400">{{ entry.created_at.strftime('%Y-%m-%d') }}</td>
        <td class="px-4 py-2 flex gap-3">
          <a href="/entries/{{ entry.id }}/edit" class="text-indigo-600 hover:underline">Edit</a>
          <form method="post" action="/entries/{{ entry.id }}/delete" class="inline">
            <button type="submit" class="text-red-600 hover:underline"
                    onclick="return confirm('Delete entry #{{ entry.id }}?')">Delete</button>
          </form>
        </td>
      </tr>
      {% else %}
      <tr><td colspan="6" class="px-4 py-8 text-center text-gray-400">No entries found.</td></tr>
      {% endfor %}
    </tbody>
  </table>
</div>
<div class="mt-4 flex gap-2 items-center">
  {% if page > 1 %}
  <a href="?q={{ q }}&author_id={{ author_id }}&page={{ page - 1 }}"
     class="px-3 py-1.5 border rounded text-sm hover:bg-gray-50">← Prev</a>
  {% endif %}
  <span class="text-sm text-gray-500">Page {{ page }}</span>
  {% if has_next %}
  <a href="?q={{ q }}&author_id={{ author_id }}&page={{ page + 1 }}"
     class="px-3 py-1.5 border rounded text-sm hover:bg-gray-50">Next →</a>
  {% endif %}
</div>
{% endblock %}
```

`lilwman/infrastructure/web/templates/entry_edit.html`:
```html
{% extends "base.html" %}
{% block title %} — Edit Entry #{{ entry.id }}{% endblock %}
{% block content %}
<div class="flex items-center gap-3 mb-6">
  <a href="/entries" class="text-gray-400 hover:text-gray-600 text-sm">← Entries</a>
  <h2 class="text-2xl font-bold">Edit Entry #{{ entry.id }}</h2>
</div>
<form method="post" action="/entries/{{ entry.id }}/edit" class="bg-white rounded-lg shadow p-6 max-w-2xl">
  <div class="mb-5">
    <label class="block font-medium text-sm mb-1.5">Content</label>
    <textarea name="content" rows="8"
              class="w-full border rounded-lg px-3 py-2 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-indigo-300">{{ entry.content }}</textarea>
  </div>
  <div class="mb-6">
    <label class="block font-medium text-sm mb-1.5">Tags <span class="text-gray-400">(comma-separated)</span></label>
    <input name="tags" value="{{ entry.tags | join(', ') }}"
           class="w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-300">
  </div>
  <div class="flex gap-3">
    <button type="submit" class="bg-indigo-600 text-white px-6 py-2 rounded-lg text-sm hover:bg-indigo-700">Save changes</button>
    <a href="/entries" class="px-6 py-2 border rounded-lg text-sm hover:bg-gray-50">Cancel</a>
  </div>
</form>
{% endblock %}
```

`lilwman/infrastructure/web/templates/feeds.html`:
```html
{% extends "base.html" %}
{% block title %} — Feeds{% endblock %}
{% block content %}
<h2 class="text-2xl font-bold mb-6">Feed Subscriptions</h2>
<div class="bg-white rounded-lg shadow overflow-hidden">
  <table class="w-full text-sm">
    <thead class="bg-gray-50 text-gray-600 uppercase text-xs">
      <tr>
        <th class="px-4 py-3 text-left w-12">ID</th>
        <th class="px-4 py-3 text-left">Platform</th>
        <th class="px-4 py-3 text-left">Account</th>
        <th class="px-4 py-3 text-left">Channel</th>
        <th class="px-4 py-3 text-left">Guild</th>
        <th class="px-4 py-3 text-left w-24">Created</th>
        <th class="px-4 py-3 text-left w-16">Actions</th>
      </tr>
    </thead>
    <tbody>
      {% for feed in feeds %}
      <tr class="border-t hover:bg-gray-50">
        <td class="px-4 py-2 text-gray-400">#{{ feed.id }}</td>
        <td class="px-4 py-2">{{ feed.platform }}</td>
        <td class="px-4 py-2">{{ feed.account_name }}</td>
        <td class="px-4 py-2 text-gray-400 text-xs">{{ feed.channel_id }}</td>
        <td class="px-4 py-2 text-gray-400 text-xs">{{ feed.guild_id }}</td>
        <td class="px-4 py-2 text-gray-400">{{ feed.created_at.strftime('%Y-%m-%d') }}</td>
        <td class="px-4 py-2">
          <form method="post" action="/feeds/{{ feed.id }}/delete" class="inline">
            <button type="submit" class="text-red-600 hover:underline text-sm"
                    onclick="return confirm('Delete feed #{{ feed.id }}?')">Delete</button>
          </form>
        </td>
      </tr>
      {% else %}
      <tr><td colspan="7" class="px-4 py-8 text-center text-gray-400">No feed subscriptions.</td></tr>
      {% endfor %}
    </tbody>
  </table>
</div>
{% endblock %}
```

`lilwman/infrastructure/web/templates/config.html`:
```html
{% extends "base.html" %}
{% block title %} — Config{% endblock %}
{% block content %}
<h2 class="text-2xl font-bold mb-6">Guild Configuration</h2>
<form method="post" action="/config" class="bg-white rounded-lg shadow p-6 max-w-lg">
  <div class="mb-6">
    <label class="flex items-start gap-3 cursor-pointer">
      <input type="checkbox" name="store_restricted" value="true"
             {% if config.store_restricted %}checked{% endif %}
             class="mt-0.5 w-4 h-4 rounded text-indigo-600">
      <div>
        <span class="font-medium text-sm">Restrict /store to administrators</span>
        <p class="text-xs text-gray-500 mt-0.5">
          When enabled, only Discord administrators can use /store to add wiki entries.
        </p>
      </div>
    </label>
  </div>
  <button type="submit" class="bg-indigo-600 text-white px-6 py-2 rounded-lg text-sm hover:bg-indigo-700">
    Save configuration
  </button>
</form>
{% endblock %}
```

- [ ] **Step 8: Run tests**

```bash
uv run pytest tests/infrastructure/test_web_routes.py -v
```
Expected: all 12 tests pass.

- [ ] **Step 9: Run full suite**

```bash
uv run pytest -q
```
Expected: all tests pass.

- [ ] **Step 10: Commit**

```bash
git add lilwman/infrastructure/web/routes/ \
        lilwman/infrastructure/web/templates/
git commit -m "feat: add web routes and templates (dashboard, entries, feeds, config)"
```

---

### Task 10: Config fields, bot wiring, and main entrypoint

**Files:**
- Modify: `lilwman/config.py`
- Modify: `lilwman/bot/bot.py`
- Modify: `lilwman/__main__.py`
- Modify: `.env.example`
- Modify: `tests/test_config.py`
- Modify: `tests/bot/test_bot.py`

**Interfaces:**
- Consumes: all use cases and repositories from Tasks 1–9; `create_app` from Task 8; `AdminCog` from Task 7
- Produces: fully wired system; web server running alongside bot via `asyncio.gather()`

- [ ] **Step 1: Write failing tests**

Add to `tests/test_config.py`:
```python
def test_web_port_default():
    from lilwman.config import Settings
    s = Settings(discord_token="t", discord_guild_id=1)
    assert s.web_port == 8080


def test_web_base_url_default():
    from lilwman.config import Settings
    s = Settings(discord_token="t", discord_guild_id=1)
    assert s.web_base_url == "http://localhost:8080"


def test_discord_client_id_default_empty():
    from lilwman.config import Settings
    s = Settings(discord_token="t", discord_guild_id=1)
    assert s.discord_client_id == ""
```

Add to `tests/bot/test_bot.py` — update `make_bot_instance()` with new kwargs:
```python
def make_bot_instance():
    return LilwmanBot(
        guild_id=1,
        store_entry=AsyncMock(),
        search_entries=AsyncMock(),
        delete_entry=AsyncMock(),
        list_by_tag=AsyncMock(),
        ask_query=AsyncMock(),
        add_feed=MagicMock(),
        remove_feed=MagicMock(),
        list_feeds=MagicMock(),
        poll_feeds=MagicMock(),
        get_stats=MagicMock(),
        get_entry=MagicMock(),
        edit_entry=MagicMock(),
        list_all_entries=MagicMock(),
        list_by_author=MagicMock(),
        purge_by_author=MagicMock(),
        purge_by_tag=MagicMock(),
        get_guild_config=MagicMock(),
        set_guild_config=MagicMock(),
    )
```

- [ ] **Step 2: Run to verify fail**

```bash
uv run pytest tests/test_config.py::test_web_port_default tests/bot/test_bot.py -v
```
Expected: `ValidationError` — unknown field `web_port` in Settings.

- [ ] **Step 3: Update `lilwman/config.py`**

```python
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    discord_token: str
    discord_guild_id: int
    ollama_host: str = "http://localhost:11434"
    ollama_model: str = "qwen2.5:1.5b"
    db_path: str = "data/lilwman.db"
    rss_bridge_url: str = "http://localhost:3000"
    discord_client_id: str = ""
    discord_client_secret: str = ""
    web_base_url: str = "http://localhost:8080"
    web_port: int = 8080
    web_secret_key: str = ""
    web_guild_id: str = ""
```

- [ ] **Step 4: Update `lilwman/bot/bot.py`** — add 9 new use case params and AdminCog

```python
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
from lilwman.application.get_stats import GetStatsUseCase
from lilwman.application.get_entry import GetEntryUseCase
from lilwman.application.edit_entry import EditEntryUseCase
from lilwman.application.list_all_entries import ListAllEntriesUseCase
from lilwman.application.list_by_author import ListByAuthorUseCase
from lilwman.application.purge_by_author import PurgeByAuthorUseCase
from lilwman.application.purge_by_tag import PurgeByTagUseCase
from lilwman.application.get_guild_config import GetGuildConfigUseCase
from lilwman.application.set_guild_config import SetGuildConfigUseCase


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
        get_stats: GetStatsUseCase,
        get_entry: GetEntryUseCase,
        edit_entry: EditEntryUseCase,
        list_all_entries: ListAllEntriesUseCase,
        list_by_author: ListByAuthorUseCase,
        purge_by_author: PurgeByAuthorUseCase,
        purge_by_tag: PurgeByTagUseCase,
        get_guild_config: GetGuildConfigUseCase,
        set_guild_config: SetGuildConfigUseCase,
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
        self.get_stats = get_stats
        self.get_entry = get_entry
        self.edit_entry = edit_entry
        self.list_all_entries = list_all_entries
        self.list_by_author = list_by_author
        self.purge_by_author = purge_by_author
        self.purge_by_tag = purge_by_tag
        self.get_guild_config = get_guild_config
        self.set_guild_config = set_guild_config

    async def setup_hook(self) -> None:
        from lilwman.bot.commands.store import StoreCog
        from lilwman.bot.commands.search import SearchCog
        from lilwman.bot.commands.delete import DeleteCog
        from lilwman.bot.commands.tag import TagCog
        from lilwman.bot.commands.ask import AskCog
        from lilwman.bot.commands.feed import FeedCog
        from lilwman.bot.commands.admin import AdminCog
        from lilwman.bot.poller import FeedPoller

        await self.add_cog(StoreCog(self))
        await self.add_cog(SearchCog(self))
        await self.add_cog(DeleteCog(self))
        await self.add_cog(TagCog(self))
        await self.add_cog(AskCog(self))
        await self.add_cog(FeedCog(self))
        await self.add_cog(AdminCog(self))
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
```

- [ ] **Step 5: Update `lilwman/__main__.py`** — create all use cases, wire web panel, asyncio.gather

```python
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
```

- [ ] **Step 6: Update `.env.example`**

```
DISCORD_TOKEN=your-bot-token-here
DISCORD_GUILD_ID=your-server-id-here
OLLAMA_HOST=http://localhost:11434
OLLAMA_MODEL=qwen2.5:1.5b
DB_PATH=/opt/lilwman/data/lilwman.db
RSS_BRIDGE_URL=http://localhost:3000
DISCORD_CLIENT_ID=your-discord-app-client-id
DISCORD_CLIENT_SECRET=your-discord-app-client-secret
WEB_BASE_URL=http://localhost:8080
WEB_PORT=8080
WEB_SECRET_KEY=
WEB_GUILD_ID=your-server-id-here
```

- [ ] **Step 7: Run tests**

```bash
uv run pytest tests/test_config.py tests/bot/test_bot.py -v
```
Expected: all pass.

- [ ] **Step 8: Run full suite**

```bash
uv run pytest -q
```
Expected: all tests pass. Coverage ≥85%.

- [ ] **Step 9: Commit**

```bash
git add lilwman/config.py \
        lilwman/bot/bot.py \
        lilwman/__main__.py \
        .env.example \
        tests/test_config.py \
        tests/bot/test_bot.py
git commit -m "feat: wire admin panel use cases into bot and web server, asyncio.gather entrypoint"
```
