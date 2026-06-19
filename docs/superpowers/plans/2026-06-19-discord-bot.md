# lilwman Discord Bot — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a single-server Discord bot with shared wiki storage (SQLite + FTS5), slash command interface, and RAG-powered `/ask` via local Ollama LLM.

**Architecture:** Clean architecture — `bot` → `application` → `domain`. Infrastructure (SQLAlchemy, Ollama) implements domain ports. Domain layer has zero framework dependencies. Bot layer only touches application use cases.

**Tech Stack:** Python 3.11+, discord.py 2.x, SQLAlchemy 2.x async, aiosqlite, alembic, pydantic-settings, ollama Python client, pytest + pytest-asyncio + pytest-cov, uv, Nix devShell, process-compose.

## Global Constraints

- Python ≥ 3.11
- discord.py ≥ 2.4
- SQLAlchemy ≥ 2.0 (async)
- `asyncio_mode = "auto"` in pytest config — no `@pytest.mark.asyncio` decorators needed
- All DB ops async via aiosqlite
- Slash commands only — no prefix commands
- Domain layer: zero imports from sqlalchemy, discord, or ollama
- FTS5 managed by app layer in same transaction as entries — no triggers
- `.env` never committed; `.env.example` always committed
- Application + infrastructure test coverage ≥ 80%
- No DB mocking in application tests — use real in-memory SQLite

## File Map

```
lilwman/                          ← Python package
├── __init__.py
├── __main__.py                   ← entry point: python -m lilwman
├── config.py                     ← pydantic-settings Settings class
├── domain/
│   ├── __init__.py
│   ├── entities.py               ← Entry dataclass
│   └── ports.py                  ← EntryRepository ABC, LLMPort ABC
├── infrastructure/
│   ├── __init__.py
│   ├── db/
│   │   ├── __init__.py
│   │   ├── models.py             ← SQLAlchemy ORM: EntryModel, TagModel
│   │   ├── session.py            ← async engine + session factory + init_db()
│   │   ├── repository.py         ← SQLAlchemyEntryRepository
│   │   └── migrations/
│   │       ├── env.py
│   │       ├── script.py.mako
│   │       └── versions/
│   │           └── 0001_initial.py
│   └── llm/
│       ├── __init__.py
│       └── ollama.py             ← OllamaLLM(LLMPort)
├── application/
│   ├── __init__.py
│   ├── store_entry.py            ← StoreEntryUseCase
│   ├── search_entries.py         ← SearchEntriesUseCase
│   ├── delete_entry.py           ← DeleteEntryUseCase
│   ├── list_by_tag.py            ← ListByTagUseCase
│   └── ask_query.py              ← AskQueryUseCase
└── bot/
    ├── __init__.py
    ├── bot.py                    ← LilwmanBot(commands.Bot)
    └── commands/
        ├── __init__.py
        ├── store.py              ← StoreCog
        ├── search.py             ← SearchCog + SearchPaginator(ui.View)
        ├── delete.py             ← DeleteCog
        ├── tag.py                ← TagCog
        └── ask.py                ← AskCog
tests/
├── __init__.py
├── domain/
│   ├── __init__.py
│   └── test_entities.py
├── application/
│   ├── __init__.py
│   ├── conftest.py               ← in-memory SQLite session_factory fixture
│   ├── test_store_entry.py
│   ├── test_search_entries.py
│   ├── test_delete_entry.py
│   ├── test_list_by_tag.py
│   └── test_ask_query.py
├── infrastructure/
│   ├── __init__.py
│   ├── conftest.py               ← tmp_path SQLite session_factory fixture
│   ├── test_repository.py
│   └── test_ollama.py
└── bot/
    ├── __init__.py
    └── test_commands.py
pyproject.toml
alembic.ini
flake.nix
process-compose.yaml
Makefile
.env.example
.gitignore
```

---

### Task 1: Project Scaffold

**Files:**
- Create: `pyproject.toml`
- Create: `flake.nix`
- Create: `process-compose.yaml`
- Create: `Makefile`
- Create: `.env.example`
- Create: `.gitignore`
- Create: `alembic.ini`
- Create all `__init__.py` stubs for the package tree above

**Interfaces:**
- Produces: `uv run python -m lilwman` entry point; `nix develop` shell; `make test`; `make deploy`

- [ ] **Step 1: Create pyproject.toml**

```toml
[project]
name = "lilwman"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "discord.py>=2.4",
    "sqlalchemy[asyncio]>=2.0",
    "aiosqlite>=0.20",
    "alembic>=1.13",
    "pydantic-settings>=2.7",
    "ollama>=0.3",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.23",
    "pytest-cov>=5.0",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["lilwman"]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]

[tool.coverage.run]
source = ["lilwman"]
omit = ["lilwman/infrastructure/db/migrations/*"]
```

- [ ] **Step 2: Create flake.nix**

```nix
{
  description = "lilwman discord bot";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs = { self, nixpkgs, flake-utils }:
    flake-utils.lib.eachDefaultSystem (system:
      let pkgs = nixpkgs.legacyPackages.${system}; in {
        devShells.default = pkgs.mkShell {
          packages = with pkgs; [
            python311
            uv
            ollama
            process-compose
          ];
        };
      });
}
```

- [ ] **Step 3: Create process-compose.yaml**

```yaml
version: "0.5"
processes:
  ollama:
    command: "ollama serve"
    readiness_probe:
      http_get:
        host: "localhost"
        path: "/"
        port: 11434
      initial_delay_seconds: 2
      period_seconds: 5
      failure_threshold: 10
  bot:
    command: "uv run python -m lilwman"
    depends_on:
      ollama:
        condition: process_healthy
    environment:
      - "PYTHONUNBUFFERED=1"
```

- [ ] **Step 4: Create Makefile**

```makefile
.PHONY: dev test deploy

dev:
	process-compose up

test:
	uv run pytest --cov=lilwman --cov-report=term-missing

deploy:
	rsync -av \
		--exclude='.venv' \
		--exclude='.env' \
		--exclude='__pycache__' \
		--exclude='*.pyc' \
		--exclude='.git' \
		. gigi:/opt/lilwman/
	ssh gigi "cd /opt/lilwman && uv sync && sudo systemctl restart lilwman"
```

- [ ] **Step 5: Create .env.example**

```
DISCORD_TOKEN=your-bot-token-here
DISCORD_GUILD_ID=your-server-id-here
OLLAMA_HOST=http://localhost:11434
OLLAMA_MODEL=qwen2.5:1.5b
DB_PATH=/opt/lilwman/data/lilwman.db
```

- [ ] **Step 6: Create .gitignore**

```
.venv/
.env
__pycache__/
*.pyc
*.pyo
.pytest_cache/
.coverage
htmlcov/
dist/
*.egg-info/
data/
```

- [ ] **Step 7: Create alembic.ini**

```ini
[alembic]
script_location = lilwman/infrastructure/db/migrations
sqlalchemy.url = sqlite+aiosqlite:///lilwman.db

[loggers]
keys = root,sqlalchemy,alembic

[handlers]
keys = console

[formatters]
keys = generic

[logger_root]
level = WARN
handlers = console
qualname =

[logger_sqlalchemy]
level = WARN
handlers =
qualname = sqlalchemy.engine

[logger_alembic]
level = INFO
handlers =
qualname = alembic

[handler_console]
class = StreamHandler
args = (sys.stderr,)
level = NOTSET
formatter = generic

[formatter_generic]
format = %(levelname)-5.5s [%(name)s] %(message)s
datefmt = %H:%M:%S
```

- [ ] **Step 8: Create package __init__.py stubs**

Create empty `__init__.py` in each directory:
```
lilwman/__init__.py
lilwman/domain/__init__.py
lilwman/infrastructure/__init__.py
lilwman/infrastructure/db/__init__.py
lilwman/infrastructure/llm/__init__.py
lilwman/application/__init__.py
lilwman/bot/__init__.py
lilwman/bot/commands/__init__.py
tests/__init__.py
tests/domain/__init__.py
tests/application/__init__.py
tests/infrastructure/__init__.py
tests/bot/__init__.py
```

All files contain only: (empty file)

- [ ] **Step 9: Install dependencies**

```bash
uv sync --extra dev
```

Expected: resolves and installs all deps, creates `uv.lock`.

- [ ] **Step 10: Commit**

```bash
git add pyproject.toml flake.nix process-compose.yaml Makefile .env.example .gitignore alembic.ini lilwman/ tests/
git commit -m "chore: project scaffold with uv, nix devshell, process-compose"
```

---

### Task 2: Config

**Files:**
- Create: `lilwman/config.py`

**Interfaces:**
- Produces: `Settings` class with fields `discord_token: str`, `discord_guild_id: int`, `ollama_host: str`, `ollama_model: str`, `db_path: str`

- [ ] **Step 1: Create lilwman/config.py**

```python
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    discord_token: str
    discord_guild_id: int
    ollama_host: str = "http://localhost:11434"
    ollama_model: str = "qwen2.5:1.5b"
    db_path: str = "data/lilwman.db"
```

- [ ] **Step 2: Verify settings loads from env**

```bash
DISCORD_TOKEN=test DISCORD_GUILD_ID=123 uv run python -c "
from lilwman.config import Settings
s = Settings()
print(s.discord_token, s.discord_guild_id)
"
```

Expected output: `test 123`

- [ ] **Step 3: Commit**

```bash
git add lilwman/config.py
git commit -m "feat: pydantic-settings config"
```

---

### Task 3: Domain Layer

**Files:**
- Create: `lilwman/domain/entities.py`
- Create: `lilwman/domain/ports.py`
- Create: `tests/domain/test_entities.py`

**Interfaces:**
- Produces:
  - `Entry(id, content, tags, author_id, author_name, created_at, updated_at)` dataclass
  - `EntryRepository` ABC with methods: `save`, `get_by_id`, `search`, `list_by_tag`, `delete`
  - `LLMPort` ABC with method: `generate`

- [ ] **Step 1: Write failing test**

```python
# tests/domain/test_entities.py
from datetime import datetime, timezone
from lilwman.domain.entities import Entry


def test_entry_has_expected_fields():
    now = datetime.now(timezone.utc)
    entry = Entry(
        id=1,
        content="some content",
        tags=["python", "nix"],
        author_id="123456789",
        author_name="cameron",
        created_at=now,
        updated_at=now,
    )
    assert entry.id == 1
    assert entry.content == "some content"
    assert entry.tags == ["python", "nix"]
    assert entry.author_id == "123456789"
    assert entry.author_name == "cameron"


def test_entry_tags_defaults_to_empty_list():
    now = datetime.now(timezone.utc)
    entry = Entry(
        id=2,
        content="no tags",
        tags=[],
        author_id="111",
        author_name="user",
        created_at=now,
        updated_at=now,
    )
    assert entry.tags == []
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/domain/test_entities.py -v
```

Expected: `ModuleNotFoundError: No module named 'lilwman.domain.entities'`

- [ ] **Step 3: Create lilwman/domain/entities.py**

```python
from dataclasses import dataclass
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
```

- [ ] **Step 4: Run test to verify it passes**

```bash
uv run pytest tests/domain/test_entities.py -v
```

Expected: `2 passed`

- [ ] **Step 5: Create lilwman/domain/ports.py**

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
    ) -> Entry: ...

    @abstractmethod
    async def get_by_id(self, entry_id: int) -> Entry | None: ...

    @abstractmethod
    async def search(self, query: str, limit: int = 20) -> list[Entry]: ...

    @abstractmethod
    async def list_by_tag(self, tag: str) -> list[Entry]: ...

    @abstractmethod
    async def delete(
        self, entry_id: int, author_id: str, is_admin: bool
    ) -> bool: ...


class LLMPort(ABC):
    @abstractmethod
    async def generate(self, prompt: str) -> str: ...
```

- [ ] **Step 6: Verify ports import cleanly**

```bash
uv run python -c "from lilwman.domain.ports import EntryRepository, LLMPort; print('ok')"
```

Expected: `ok`

- [ ] **Step 7: Commit**

```bash
git add lilwman/domain/ tests/domain/
git commit -m "feat: domain entities and port interfaces"
```

---

### Task 4: DB Models, Session, and Migrations

**Files:**
- Create: `lilwman/infrastructure/db/models.py`
- Create: `lilwman/infrastructure/db/session.py`
- Create: `lilwman/infrastructure/db/migrations/env.py`
- Create: `lilwman/infrastructure/db/migrations/script.py.mako`
- Create: `lilwman/infrastructure/db/migrations/versions/0001_initial.py`

**Interfaces:**
- Produces:
  - `EntryModel`, `TagModel` SQLAlchemy models
  - `create_engine(db_path: str) -> AsyncEngine`
  - `create_session_factory(engine) -> async_sessionmaker`
  - `init_db(engine) -> None` — runs migrations / creates tables

- [ ] **Step 1: Create lilwman/infrastructure/db/models.py**

```python
from datetime import datetime, timezone
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

- [ ] **Step 2: Create lilwman/infrastructure/db/session.py**

```python
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
```

- [ ] **Step 3: Create migrations/env.py**

```python
import asyncio
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.ext.asyncio import create_async_engine

from alembic import context

from lilwman.infrastructure.db.models import Base

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def do_run_migrations(connection):
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        render_as_batch=True,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    url = config.get_main_option("sqlalchemy.url")
    connectable = create_async_engine(url, poolclass=pool.NullPool)
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True,
    )
    with context.begin_transaction():
        context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
```

- [ ] **Step 4: Create migrations/script.py.mako**

```
"""${message}

Revision ID: ${up_revision}
Revises: ${down_revision | comma,n}
Create Date: ${create_date}

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
${imports if imports else ""}

revision: str = ${repr(up_revision)}
down_revision: Union[str, None] = ${repr(down_revision)}
branch_labels: Union[str, Sequence[str], None] = ${repr(branch_labels)}
depends_on: Union[str, Sequence[str], None] = ${repr(depends_on)}


def upgrade() -> None:
    ${upgrades if upgrades else "pass"}


def downgrade() -> None:
    ${downgrades if downgrades else "pass"}
```

- [ ] **Step 5: Create migrations/versions/0001_initial.py**

```python
"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-06-19

"""
from typing import Sequence, Union
import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "entries",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("author_id", sa.String(), nullable=False),
        sa.Column("author_name", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_table(
        "tags",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("entry_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.ForeignKeyConstraint(["entry_id"], ["entries.id"], ondelete="CASCADE"),
    )
    op.execute(
        """
        CREATE VIRTUAL TABLE entries_fts USING fts5(
            entry_id UNINDEXED,
            content,
            tags
        )
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS entries_fts")
    op.drop_table("tags")
    op.drop_table("entries")
```

- [ ] **Step 6: Create migrations/__init__.py**

Empty file.

- [ ] **Step 7: Verify session module imports**

```bash
uv run python -c "from lilwman.infrastructure.db.session import create_engine, create_session_factory, init_db; print('ok')"
```

Expected: `ok`

- [ ] **Step 8: Commit**

```bash
git add lilwman/infrastructure/db/ alembic.ini
git commit -m "feat: SQLAlchemy models, async session, alembic migration"
```

---

### Task 5: Entry Repository

**Files:**
- Create: `lilwman/infrastructure/db/repository.py`
- Create: `tests/infrastructure/conftest.py`
- Create: `tests/infrastructure/test_repository.py`

**Interfaces:**
- Consumes: `EntryRepository` (domain/ports.py), `EntryModel`/`TagModel` (db/models.py), `async_sessionmaker` (db/session.py)
- Produces: `SQLAlchemyEntryRepository(EntryRepository)` — concrete implementation

- [ ] **Step 1: Create tests/infrastructure/conftest.py**

```python
import pytest
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy import text

from lilwman.infrastructure.db.models import Base


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
```

- [ ] **Step 2: Write failing tests**

```python
# tests/infrastructure/test_repository.py
import pytest
from lilwman.infrastructure.db.repository import SQLAlchemyEntryRepository


@pytest.fixture
def repo(session_factory):
    return SQLAlchemyEntryRepository(session_factory)


async def test_save_returns_entry_with_id(repo):
    entry = await repo.save(
        content="hello world",
        tags=["greet"],
        author_id="111",
        author_name="alice",
    )
    assert entry.id is not None
    assert entry.content == "hello world"
    assert entry.tags == ["greet"]
    assert entry.author_id == "111"


async def test_get_by_id_returns_saved_entry(repo):
    saved = await repo.save(
        content="nix is great",
        tags=["nix"],
        author_id="222",
        author_name="bob",
    )
    fetched = await repo.get_by_id(saved.id)
    assert fetched is not None
    assert fetched.id == saved.id
    assert fetched.content == "nix is great"
    assert fetched.tags == ["nix"]


async def test_get_by_id_returns_none_for_missing(repo):
    result = await repo.get_by_id(9999)
    assert result is None


async def test_search_finds_matching_entry(repo):
    await repo.save(content="python is fun", tags=["python"], author_id="1", author_name="a")
    await repo.save(content="nix flakes rock", tags=["nix"], author_id="2", author_name="b")
    results = await repo.search("python")
    assert len(results) == 1
    assert results[0].content == "python is fun"


async def test_search_returns_empty_for_no_match(repo):
    await repo.save(content="unrelated stuff", tags=[], author_id="1", author_name="a")
    results = await repo.search("zzznomatch")
    assert results == []


async def test_list_by_tag_returns_entries_with_tag(repo):
    await repo.save(content="entry one", tags=["alpha", "beta"], author_id="1", author_name="a")
    await repo.save(content="entry two", tags=["beta"], author_id="2", author_name="b")
    await repo.save(content="entry three", tags=["gamma"], author_id="3", author_name="c")
    results = await repo.list_by_tag("beta")
    assert len(results) == 2


async def test_delete_own_entry_succeeds(repo):
    entry = await repo.save(content="to delete", tags=[], author_id="111", author_name="me")
    deleted = await repo.delete(entry.id, author_id="111", is_admin=False)
    assert deleted is True
    assert await repo.get_by_id(entry.id) is None


async def test_delete_other_entry_fails_without_admin(repo):
    entry = await repo.save(content="not mine", tags=[], author_id="999", author_name="other")
    deleted = await repo.delete(entry.id, author_id="111", is_admin=False)
    assert deleted is False
    assert await repo.get_by_id(entry.id) is not None


async def test_delete_any_entry_succeeds_as_admin(repo):
    entry = await repo.save(content="admin can delete", tags=[], author_id="999", author_name="other")
    deleted = await repo.delete(entry.id, author_id="111", is_admin=True)
    assert deleted is True
    assert await repo.get_by_id(entry.id) is None
```

- [ ] **Step 3: Run tests to verify they fail**

```bash
uv run pytest tests/infrastructure/test_repository.py -v
```

Expected: `ImportError` — `repository` module not found.

- [ ] **Step 4: Create lilwman/infrastructure/db/repository.py**

```python
from datetime import datetime, timezone

from sqlalchemy import select, text
from sqlalchemy.orm import selectinload

from lilwman.domain.entities import Entry
from lilwman.domain.ports import EntryRepository
from .models import EntryModel, TagModel


class SQLAlchemyEntryRepository(EntryRepository):
    def __init__(self, session_factory):
        self._session_factory = session_factory

    async def save(
        self,
        content: str,
        tags: list[str],
        author_id: str,
        author_name: str,
    ) -> Entry:
        now = datetime.now(timezone.utc)
        clean_tags = [t.strip() for t in tags if t.strip()]
        async with self._session_factory() as session:
            async with session.begin():
                entry_model = EntryModel(
                    content=content,
                    author_id=author_id,
                    author_name=author_name,
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
            created_at=now,
            updated_at=now,
        )

    async def get_by_id(self, entry_id: int) -> Entry | None:
        async with self._session_factory() as session:
            result = await session.execute(
                select(EntryModel)
                .options(selectinload(EntryModel.tags))
                .where(EntryModel.id == entry_id)
            )
            model = result.scalar_one_or_none()
            if model is None:
                return None
            return self._to_entity(model)

    async def search(self, query: str, limit: int = 20) -> list[Entry]:
        async with self._session_factory() as session:
            rows = (
                await session.execute(
                    text(
                        """
                        SELECT e.id FROM entries_fts f
                        JOIN entries e ON e.id = f.entry_id
                        WHERE entries_fts MATCH :q
                        ORDER BY rank
                        LIMIT :lim
                        """
                    ),
                    {"q": query, "lim": limit},
                )
            ).fetchall()

            if not rows:
                return []

            ids = [r[0] for r in rows]
            result = await session.execute(
                select(EntryModel)
                .options(selectinload(EntryModel.tags))
                .where(EntryModel.id.in_(ids))
            )
            models_by_id = {m.id: m for m in result.scalars().all()}
            return [self._to_entity(models_by_id[i]) for i in ids if i in models_by_id]

    async def list_by_tag(self, tag: str) -> list[Entry]:
        async with self._session_factory() as session:
            result = await session.execute(
                select(EntryModel)
                .options(selectinload(EntryModel.tags))
                .join(TagModel)
                .where(TagModel.name == tag)
                .order_by(EntryModel.created_at.desc())
            )
            return [self._to_entity(m) for m in result.scalars().unique().all()]

    async def delete(
        self, entry_id: int, author_id: str, is_admin: bool
    ) -> bool:
        async with self._session_factory() as session:
            async with session.begin():
                result = await session.execute(
                    select(EntryModel).where(EntryModel.id == entry_id)
                )
                model = result.scalar_one_or_none()
                if model is None:
                    return False
                if not is_admin and model.author_id != author_id:
                    return False
                await session.delete(model)
                await session.execute(
                    text("DELETE FROM entries_fts WHERE entry_id = :eid"),
                    {"eid": entry_id},
                )
                return True

    def _to_entity(self, model: EntryModel) -> Entry:
        return Entry(
            id=model.id,
            content=model.content,
            tags=[t.name for t in model.tags],
            author_id=model.author_id,
            author_name=model.author_name,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
uv run pytest tests/infrastructure/test_repository.py -v
```

Expected: `9 passed`

- [ ] **Step 6: Commit**

```bash
git add lilwman/infrastructure/db/repository.py tests/infrastructure/
git commit -m "feat: SQLAlchemy entry repository with FTS5 sync"
```

---

### Task 6: Store, Delete, ListByTag Use Cases

**Files:**
- Create: `lilwman/application/store_entry.py`
- Create: `lilwman/application/delete_entry.py`
- Create: `lilwman/application/list_by_tag.py`
- Create: `tests/application/conftest.py`
- Create: `tests/application/test_store_entry.py`
- Create: `tests/application/test_delete_entry.py`
- Create: `tests/application/test_list_by_tag.py`

**Interfaces:**
- Consumes: `EntryRepository` port
- Produces:
  - `StoreEntryUseCase.execute(content, tags, author_id, author_name) -> Entry`
  - `DeleteEntryUseCase.execute(entry_id, author_id, is_admin) -> bool`
  - `ListByTagUseCase.execute(tag) -> list[Entry]`

- [ ] **Step 1: Create tests/application/conftest.py**

```python
import pytest
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy import text

from lilwman.infrastructure.db.models import Base
from lilwman.infrastructure.db.repository import SQLAlchemyEntryRepository


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
```

- [ ] **Step 2: Write failing tests**

```python
# tests/application/test_store_entry.py
import pytest
from lilwman.application.store_entry import StoreEntryUseCase


@pytest.fixture
def use_case(repo):
    return StoreEntryUseCase(repo)


async def test_store_entry_returns_entry(use_case):
    entry = await use_case.execute(
        content="discord is cool",
        tags=["discord"],
        author_id="1",
        author_name="alice",
    )
    assert entry.id is not None
    assert entry.content == "discord is cool"
    assert entry.tags == ["discord"]


async def test_store_entry_with_no_tags(use_case):
    entry = await use_case.execute(
        content="no tags here",
        tags=[],
        author_id="1",
        author_name="alice",
    )
    assert entry.tags == []
```

```python
# tests/application/test_delete_entry.py
import pytest
from lilwman.application.store_entry import StoreEntryUseCase
from lilwman.application.delete_entry import DeleteEntryUseCase


@pytest.fixture
def store(repo):
    return StoreEntryUseCase(repo)


@pytest.fixture
def delete(repo):
    return DeleteEntryUseCase(repo)


async def test_delete_own_entry(store, delete):
    entry = await store.execute("my entry", [], "111", "alice")
    result = await delete.execute(entry.id, author_id="111", is_admin=False)
    assert result is True


async def test_delete_other_entry_denied(store, delete):
    entry = await store.execute("your entry", [], "999", "bob")
    result = await delete.execute(entry.id, author_id="111", is_admin=False)
    assert result is False


async def test_delete_any_entry_as_admin(store, delete):
    entry = await store.execute("anyone's entry", [], "999", "bob")
    result = await delete.execute(entry.id, author_id="111", is_admin=True)
    assert result is True


async def test_delete_nonexistent_entry_returns_false(delete):
    result = await delete.execute(9999, author_id="111", is_admin=True)
    assert result is False
```

```python
# tests/application/test_list_by_tag.py
import pytest
from lilwman.application.store_entry import StoreEntryUseCase
from lilwman.application.list_by_tag import ListByTagUseCase


@pytest.fixture
def store(repo):
    return StoreEntryUseCase(repo)


@pytest.fixture
def list_tag(repo):
    return ListByTagUseCase(repo)


async def test_list_by_tag_returns_matching(store, list_tag):
    await store.execute("entry a", ["alpha"], "1", "a")
    await store.execute("entry b", ["alpha", "beta"], "2", "b")
    await store.execute("entry c", ["gamma"], "3", "c")
    results = await list_tag.execute("alpha")
    assert len(results) == 2


async def test_list_by_tag_empty_for_no_match(list_tag):
    results = await list_tag.execute("nonexistent")
    assert results == []
```

- [ ] **Step 3: Run tests to verify they fail**

```bash
uv run pytest tests/application/test_store_entry.py tests/application/test_delete_entry.py tests/application/test_list_by_tag.py -v
```

Expected: `ImportError` — use case modules not found.

- [ ] **Step 4: Create use case files**

```python
# lilwman/application/store_entry.py
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
    ) -> Entry:
        return await self._repo.save(content, tags, author_id, author_name)
```

```python
# lilwman/application/delete_entry.py
from lilwman.domain.ports import EntryRepository


class DeleteEntryUseCase:
    def __init__(self, repo: EntryRepository) -> None:
        self._repo = repo

    async def execute(
        self, entry_id: int, author_id: str, is_admin: bool
    ) -> bool:
        return await self._repo.delete(entry_id, author_id, is_admin)
```

```python
# lilwman/application/list_by_tag.py
from lilwman.domain.entities import Entry
from lilwman.domain.ports import EntryRepository


class ListByTagUseCase:
    def __init__(self, repo: EntryRepository) -> None:
        self._repo = repo

    async def execute(self, tag: str) -> list[Entry]:
        return await self._repo.list_by_tag(tag)
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
uv run pytest tests/application/test_store_entry.py tests/application/test_delete_entry.py tests/application/test_list_by_tag.py -v
```

Expected: `9 passed`

- [ ] **Step 6: Commit**

```bash
git add lilwman/application/store_entry.py lilwman/application/delete_entry.py lilwman/application/list_by_tag.py tests/application/
git commit -m "feat: store, delete, list-by-tag use cases"
```

---

### Task 7: Search Use Case

**Files:**
- Create: `lilwman/application/search_entries.py`
- Create: `tests/application/test_search_entries.py`

**Interfaces:**
- Consumes: `EntryRepository` port
- Produces: `SearchEntriesUseCase.execute(query: str) -> list[Entry]` — up to 20 FTS5-ranked results

- [ ] **Step 1: Write failing test**

```python
# tests/application/test_search_entries.py
import pytest
from lilwman.application.store_entry import StoreEntryUseCase
from lilwman.application.search_entries import SearchEntriesUseCase


@pytest.fixture
def store(repo):
    return StoreEntryUseCase(repo)


@pytest.fixture
def search(repo):
    return SearchEntriesUseCase(repo)


async def test_search_finds_content_match(store, search):
    await store.execute("python decorators explained", ["python"], "1", "a")
    await store.execute("nix flakes tutorial", ["nix"], "2", "b")
    results = await search.execute("python")
    assert len(results) == 1
    assert "python" in results[0].content


async def test_search_finds_tag_match(store, search):
    await store.execute("some content", ["nix", "flakes"], "1", "a")
    results = await search.execute("flakes")
    assert len(results) == 1


async def test_search_returns_empty_for_no_match(store, search):
    await store.execute("irrelevant content", ["misc"], "1", "a")
    results = await search.execute("zzznomatch")
    assert results == []


async def test_search_returns_multiple_ranked_results(store, search):
    await store.execute("python is great for scripting", ["python"], "1", "a")
    await store.execute("python also works for web", ["python", "web"], "2", "b")
    await store.execute("javascript for web", ["js"], "3", "c")
    results = await search.execute("python")
    assert len(results) == 2
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/application/test_search_entries.py -v
```

Expected: `ImportError`

- [ ] **Step 3: Create lilwman/application/search_entries.py**

```python
from lilwman.domain.entities import Entry
from lilwman.domain.ports import EntryRepository


class SearchEntriesUseCase:
    def __init__(self, repo: EntryRepository) -> None:
        self._repo = repo

    async def execute(self, query: str) -> list[Entry]:
        return await self._repo.search(query, limit=20)
```

- [ ] **Step 4: Run test to verify it passes**

```bash
uv run pytest tests/application/test_search_entries.py -v
```

Expected: `4 passed`

- [ ] **Step 5: Commit**

```bash
git add lilwman/application/search_entries.py tests/application/test_search_entries.py
git commit -m "feat: search entries use case with FTS5"
```

---

### Task 8: Ollama LLM Adapter

**Files:**
- Create: `lilwman/infrastructure/llm/ollama.py`
- Create: `tests/infrastructure/test_ollama.py`

**Interfaces:**
- Consumes: `LLMPort` ABC, `Settings.ollama_host`, `Settings.ollama_model`
- Produces: `OllamaLLM(LLMPort)` with `async generate(prompt: str) -> str`

- [ ] **Step 1: Write failing test**

```python
# tests/infrastructure/test_ollama.py
from unittest.mock import AsyncMock, patch, MagicMock
import pytest
from lilwman.infrastructure.llm.ollama import OllamaLLM


@pytest.fixture
def llm():
    return OllamaLLM(host="http://localhost:11434", model="qwen2.5:1.5b")


async def test_generate_returns_string(llm):
    mock_response = MagicMock()
    mock_response.response = "Paris is the capital of France."

    with patch(
        "lilwman.infrastructure.llm.ollama.ollama.AsyncClient"
    ) as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.generate = AsyncMock(return_value=mock_response)
        mock_client_cls.return_value = mock_client

        result = await llm.generate("What is the capital of France?")

    assert result == "Paris is the capital of France."
    mock_client.generate.assert_called_once_with(
        model="qwen2.5:1.5b",
        prompt="What is the capital of France?",
    )


async def test_generate_uses_configured_model():
    llm = OllamaLLM(host="http://localhost:11434", model="qwen2.5:0.5b")
    mock_response = MagicMock()
    mock_response.response = "answer"

    with patch(
        "lilwman.infrastructure.llm.ollama.ollama.AsyncClient"
    ) as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.generate = AsyncMock(return_value=mock_response)
        mock_client_cls.return_value = mock_client

        await llm.generate("test prompt")

    mock_client.generate.assert_called_once_with(
        model="qwen2.5:0.5b",
        prompt="test prompt",
    )
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/infrastructure/test_ollama.py -v
```

Expected: `ImportError`

- [ ] **Step 3: Create lilwman/infrastructure/llm/ollama.py**

```python
import ollama

from lilwman.domain.ports import LLMPort


class OllamaLLM(LLMPort):
    def __init__(self, host: str, model: str) -> None:
        self._host = host
        self._model = model

    async def generate(self, prompt: str) -> str:
        client = ollama.AsyncClient(host=self._host)
        response = await client.generate(model=self._model, prompt=prompt)
        return response.response
```

- [ ] **Step 4: Run test to verify it passes**

```bash
uv run pytest tests/infrastructure/test_ollama.py -v
```

Expected: `2 passed`

- [ ] **Step 5: Commit**

```bash
git add lilwman/infrastructure/llm/ollama.py tests/infrastructure/test_ollama.py
git commit -m "feat: Ollama LLM adapter"
```

---

### Task 9: Ask Query Use Case (RAG)

**Files:**
- Create: `lilwman/application/ask_query.py`
- Create: `tests/application/test_ask_query.py`

**Interfaces:**
- Consumes: `EntryRepository` port, `LLMPort`
- Produces: `AskQueryUseCase.execute(question: str) -> str` — synthesized answer or "Nothing in the wiki about that."

- [ ] **Step 1: Write failing test**

```python
# tests/application/test_ask_query.py
from unittest.mock import AsyncMock
import pytest
from lilwman.application.store_entry import StoreEntryUseCase
from lilwman.application.ask_query import AskQueryUseCase


@pytest.fixture
def store(repo):
    return StoreEntryUseCase(repo)


@pytest.fixture
def mock_llm():
    llm = AsyncMock()
    llm.generate = AsyncMock(return_value="Paris is the capital of France.")
    return llm


@pytest.fixture
def ask(repo, mock_llm):
    return AskQueryUseCase(repo, mock_llm)


async def test_ask_returns_llm_answer_when_results_found(store, ask, mock_llm):
    await store.execute("France capital is Paris", ["geography"], "1", "a")
    answer = await ask.execute("What is the capital of France?")
    assert answer == "Paris is the capital of France."
    mock_llm.generate.assert_called_once()


async def test_ask_returns_not_found_when_no_wiki_entries(ask, mock_llm):
    answer = await ask.execute("Who invented the internet?")
    assert answer == "Nothing in the wiki about that."
    mock_llm.generate.assert_not_called()


async def test_ask_prompt_includes_wiki_entries(store, ask, mock_llm):
    await store.execute("The sky is blue", ["science"], "1", "a")
    await ask.execute("Why is the sky blue?")
    prompt = mock_llm.generate.call_args[0][0]
    assert "The sky is blue" in prompt
    assert "Why is the sky blue?" in prompt
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/application/test_ask_query.py -v
```

Expected: `ImportError`

- [ ] **Step 3: Create lilwman/application/ask_query.py**

```python
from lilwman.domain.ports import EntryRepository, LLMPort


class AskQueryUseCase:
    def __init__(self, repo: EntryRepository, llm: LLMPort) -> None:
        self._repo = repo
        self._llm = llm

    async def execute(self, question: str) -> str:
        entries = await self._repo.search(question, limit=5)
        if not entries:
            return "Nothing in the wiki about that."

        snippets = "\n\n".join(
            f"[{i+1}] (tags: {', '.join(e.tags) or 'none'})\n{e.content}"
            for i, e in enumerate(entries)
        )
        prompt = (
            "You are a helpful assistant. Answer the question using only the "
            "provided wiki entries. Be concise.\n\n"
            f"Wiki entries:\n{snippets}\n\n"
            f"Question: {question}\n"
            "Answer:"
        )
        return await self._llm.generate(prompt)
```

- [ ] **Step 4: Run test to verify it passes**

```bash
uv run pytest tests/application/test_ask_query.py -v
```

Expected: `3 passed`

- [ ] **Step 5: Run full test suite and check coverage**

```bash
uv run pytest --cov=lilwman --cov-report=term-missing
```

Expected: all tests pass, application + infrastructure coverage ≥ 80%.

- [ ] **Step 6: Commit**

```bash
git add lilwman/application/ask_query.py tests/application/test_ask_query.py
git commit -m "feat: ask query use case with RAG over FTS5 results"
```

---

### Task 10: Bot Setup and Composition Root

**Files:**
- Create: `lilwman/bot/bot.py`
- Create: `lilwman/__main__.py`

**Interfaces:**
- Consumes: all use cases, `Settings`, `create_engine`, `create_session_factory`, `init_db`, `OllamaLLM`, `SQLAlchemyEntryRepository`
- Produces: `LilwmanBot` class; `python -m lilwman` starts the bot

- [ ] **Step 1: Create lilwman/bot/bot.py**

```python
import discord
from discord import app_commands
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
```

- [ ] **Step 2: Create lilwman/__main__.py**

```python
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

    os.makedirs(os.path.dirname(settings.db_path), exist_ok=True)

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
```

- [ ] **Step 3: Verify composition root imports cleanly**

```bash
DISCORD_TOKEN=x DISCORD_GUILD_ID=1 uv run python -c "
import asyncio
from lilwman.__main__ import main
print('imports ok')
"
```

Expected: `imports ok`

- [ ] **Step 4: Commit**

```bash
git add lilwman/bot/bot.py lilwman/__main__.py
git commit -m "feat: bot setup and composition root"
```

---

### Task 11: /store Command

**Files:**
- Create: `lilwman/bot/commands/store.py`
- Create: `tests/bot/test_commands.py` (initial, for /store)

**Interfaces:**
- Consumes: `LilwmanBot.store_entry: StoreEntryUseCase`
- Produces: `/store content tags?` slash command

- [ ] **Step 1: Write failing test**

```python
# tests/bot/test_commands.py
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime, timezone
import pytest
import discord

from lilwman.domain.entities import Entry
from lilwman.bot.commands.store import StoreCog


def make_bot(store_entry=None, search_entries=None, delete_entry=None,
             list_by_tag=None, ask_query=None):
    bot = MagicMock()
    bot.store_entry = store_entry or AsyncMock()
    bot.search_entries = search_entries or AsyncMock()
    bot.delete_entry = delete_entry or AsyncMock()
    bot.list_by_tag = list_by_tag or AsyncMock()
    bot.ask_query = ask_query or AsyncMock()
    return bot


def make_interaction(user_id="111", username="alice", is_admin=False):
    interaction = AsyncMock(spec=discord.Interaction)
    interaction.user = MagicMock()
    interaction.user.id = user_id
    interaction.user.display_name = username
    interaction.user.guild_permissions = MagicMock()
    interaction.user.guild_permissions.administrator = is_admin
    interaction.response = AsyncMock()
    return interaction


def make_entry(**kwargs):
    defaults = dict(
        id=1,
        content="test content",
        tags=[],
        author_id="111",
        author_name="alice",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    return Entry(**{**defaults, **kwargs})


async def test_store_command_replies_with_entry_id():
    entry = make_entry(id=42, content="hello world", tags=["greet"])
    store_uc = AsyncMock()
    store_uc.execute = AsyncMock(return_value=entry)
    bot = make_bot(store_entry=store_uc)

    cog = StoreCog(bot)
    interaction = make_interaction()

    await cog.store.callback(cog, interaction, content="hello world", tags="greet")

    interaction.response.send_message.assert_called_once()
    call_args = interaction.response.send_message.call_args
    assert "42" in str(call_args)


async def test_store_command_passes_tags_to_use_case():
    entry = make_entry(id=1, tags=["a", "b"])
    store_uc = AsyncMock()
    store_uc.execute = AsyncMock(return_value=entry)
    bot = make_bot(store_entry=store_uc)

    cog = StoreCog(bot)
    interaction = make_interaction()

    await cog.store.callback(cog, interaction, content="content", tags="a, b")

    store_uc.execute.assert_called_once_with(
        content="content",
        tags=["a", "b"],
        author_id="111",
        author_name="alice",
    )
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/bot/test_commands.py -v
```

Expected: `ImportError`

- [ ] **Step 3: Create lilwman/bot/commands/store.py**

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
        tag_list = [t.strip() for t in tags.split(",") if t.strip()]
        entry = await self.bot.store_entry.execute(
            content=content,
            tags=tag_list,
            author_id=str(interaction.user.id),
            author_name=interaction.user.display_name,
        )
        tag_display = f" [{', '.join(entry.tags)}]" if entry.tags else ""
        await interaction.response.send_message(
            f"Stored entry **#{entry.id}**{tag_display}."
        )
```

- [ ] **Step 4: Run test to verify it passes**

```bash
uv run pytest tests/bot/test_commands.py -v
```

Expected: `2 passed`

- [ ] **Step 5: Commit**

```bash
git add lilwman/bot/commands/store.py tests/bot/test_commands.py
git commit -m "feat: /store slash command"
```

---

### Task 12: /search, /tag, /delete Commands

**Files:**
- Create: `lilwman/bot/commands/search.py`
- Create: `lilwman/bot/commands/tag.py`
- Create: `lilwman/bot/commands/delete.py`
- Modify: `tests/bot/test_commands.py` (add tests for these commands)

**Interfaces:**
- Consumes: `LilwmanBot.search_entries`, `LilwmanBot.list_by_tag`, `LilwmanBot.delete_entry`
- Produces: `/search query`, `/tag name`, `/delete id` slash commands

- [ ] **Step 1: Add tests to tests/bot/test_commands.py**

Append to the existing file:

```python
# --- /search ---
from lilwman.bot.commands.search import SearchCog


async def test_search_sends_embed_with_results():
    entries = [
        make_entry(id=i, content=f"result {i}", tags=["t"]) for i in range(1, 4)
    ]
    search_uc = AsyncMock()
    search_uc.execute = AsyncMock(return_value=entries)
    bot = make_bot(search_entries=search_uc)

    cog = SearchCog(bot)
    interaction = make_interaction()

    await cog.search.callback(cog, interaction, query="test")

    interaction.response.send_message.assert_called_once()
    kwargs = interaction.response.send_message.call_args.kwargs
    assert "embed" in kwargs or len(interaction.response.send_message.call_args.args) > 0


async def test_search_no_results_sends_message():
    search_uc = AsyncMock()
    search_uc.execute = AsyncMock(return_value=[])
    bot = make_bot(search_entries=search_uc)

    cog = SearchCog(bot)
    interaction = make_interaction()

    await cog.search.callback(cog, interaction, query="nothing")

    interaction.response.send_message.assert_called_once()
    call_str = str(interaction.response.send_message.call_args)
    assert "no results" in call_str.lower() or "nothing" in call_str.lower()


# --- /delete ---
from lilwman.bot.commands.delete import DeleteCog


async def test_delete_own_entry_sends_success():
    delete_uc = AsyncMock()
    delete_uc.execute = AsyncMock(return_value=True)
    bot = make_bot(delete_entry=delete_uc)

    cog = DeleteCog(bot)
    interaction = make_interaction(user_id="111")

    await cog.delete.callback(cog, interaction, id=5)

    delete_uc.execute.assert_called_once_with(
        entry_id=5, author_id="111", is_admin=False
    )
    interaction.response.send_message.assert_called_once()


async def test_delete_denied_sends_error():
    delete_uc = AsyncMock()
    delete_uc.execute = AsyncMock(return_value=False)
    bot = make_bot(delete_entry=delete_uc)

    cog = DeleteCog(bot)
    interaction = make_interaction(user_id="111")

    await cog.delete.callback(cog, interaction, id=99)

    call_str = str(interaction.response.send_message.call_args)
    assert "not found" in call_str.lower() or "permission" in call_str.lower() or "denied" in call_str.lower()


# --- /tag ---
from lilwman.bot.commands.tag import TagCog


async def test_tag_sends_embed_with_entries():
    entries = [make_entry(id=1, content="tagged entry", tags=["nix"])]
    list_uc = AsyncMock()
    list_uc.execute = AsyncMock(return_value=entries)
    bot = make_bot(list_by_tag=list_uc)

    cog = TagCog(bot)
    interaction = make_interaction()

    await cog.tag.callback(cog, interaction, name="nix")

    list_uc.execute.assert_called_once_with("nix")
    interaction.response.send_message.assert_called_once()


async def test_tag_no_entries_sends_message():
    list_uc = AsyncMock()
    list_uc.execute = AsyncMock(return_value=[])
    bot = make_bot(list_by_tag=list_uc)

    cog = TagCog(bot)
    interaction = make_interaction()

    await cog.tag.callback(cog, interaction, name="unknown")

    call_str = str(interaction.response.send_message.call_args)
    assert "no entries" in call_str.lower() or "nothing" in call_str.lower()
```

- [ ] **Step 2: Run new tests to verify they fail**

```bash
uv run pytest tests/bot/test_commands.py -v
```

Expected: `ImportError` on `SearchCog`, `DeleteCog`, `TagCog`.

- [ ] **Step 3: Create lilwman/bot/commands/search.py**

```python
import discord
from discord import app_commands
from discord.ext import commands

from lilwman.domain.entities import Entry

PER_PAGE = 5


class SearchPaginator(discord.ui.View):
    def __init__(self, results: list[Entry], query: str) -> None:
        super().__init__(timeout=60)
        self.results = results
        self.query = query
        self.page = 0

    @property
    def total_pages(self) -> int:
        return max(1, (len(self.results) + PER_PAGE - 1) // PER_PAGE)

    def make_embed(self) -> discord.Embed:
        start = self.page * PER_PAGE
        page_entries = self.results[start : start + PER_PAGE]
        embed = discord.Embed(
            title=f"Search: {self.query}",
            color=0x5865F2,
        )
        for entry in page_entries:
            tags = ", ".join(entry.tags) if entry.tags else "no tags"
            embed.add_field(
                name=f"#{entry.id} — {entry.author_name} [{tags}]",
                value=entry.content[:200],
                inline=False,
            )
        embed.set_footer(text=f"Page {self.page + 1}/{self.total_pages}")
        return embed

    @discord.ui.button(label="◀", style=discord.ButtonStyle.secondary)
    async def prev(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        self.page = max(0, self.page - 1)
        await interaction.response.edit_message(embed=self.make_embed(), view=self)

    @discord.ui.button(label="▶", style=discord.ButtonStyle.secondary)
    async def next(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        self.page = min(self.total_pages - 1, self.page + 1)
        await interaction.response.edit_message(embed=self.make_embed(), view=self)


class SearchCog(commands.Cog):
    def __init__(self, bot) -> None:
        self.bot = bot

    @app_commands.command(name="search", description="Search the wiki")
    @app_commands.describe(query="Keywords to search for")
    async def search(self, interaction: discord.Interaction, query: str) -> None:
        results = await self.bot.search_entries.execute(query)
        if not results:
            await interaction.response.send_message(
                f"No results for **{query}**.", ephemeral=True
            )
            return
        paginator = SearchPaginator(results, query)
        await interaction.response.send_message(
            embed=paginator.make_embed(), view=paginator
        )
```

- [ ] **Step 4: Create lilwman/bot/commands/delete.py**

```python
import discord
from discord import app_commands
from discord.ext import commands


class DeleteCog(commands.Cog):
    def __init__(self, bot) -> None:
        self.bot = bot

    @app_commands.command(name="delete", description="Delete a wiki entry")
    @app_commands.describe(id="ID of the entry to delete")
    async def delete(self, interaction: discord.Interaction, id: int) -> None:
        is_admin = interaction.user.guild_permissions.administrator
        deleted = await self.bot.delete_entry.execute(
            entry_id=id,
            author_id=str(interaction.user.id),
            is_admin=is_admin,
        )
        if deleted:
            await interaction.response.send_message(
                f"Deleted entry **#{id}**.", ephemeral=True
            )
        else:
            await interaction.response.send_message(
                f"Entry **#{id}** not found or permission denied.", ephemeral=True
            )
```

- [ ] **Step 5: Create lilwman/bot/commands/tag.py**

```python
import discord
from discord import app_commands
from discord.ext import commands


class TagCog(commands.Cog):
    def __init__(self, bot) -> None:
        self.bot = bot

    @app_commands.command(name="tag", description="List entries with a tag")
    @app_commands.describe(name="Tag name to list")
    async def tag(self, interaction: discord.Interaction, name: str) -> None:
        entries = await self.bot.list_by_tag.execute(name)
        if not entries:
            await interaction.response.send_message(
                f"No entries tagged **{name}**.", ephemeral=True
            )
            return
        embed = discord.Embed(title=f"Tag: {name}", color=0x57F287)
        for entry in entries[:10]:
            embed.add_field(
                name=f"#{entry.id} — {entry.author_name}",
                value=entry.content[:200],
                inline=False,
            )
        if len(entries) > 10:
            embed.set_footer(text=f"Showing 10 of {len(entries)} entries")
        await interaction.response.send_message(embed=embed)
```

- [ ] **Step 6: Run tests to verify they pass**

```bash
uv run pytest tests/bot/test_commands.py -v
```

Expected: all tests pass (store + search + delete + tag).

- [ ] **Step 7: Commit**

```bash
git add lilwman/bot/commands/search.py lilwman/bot/commands/delete.py lilwman/bot/commands/tag.py tests/bot/test_commands.py
git commit -m "feat: /search, /delete, /tag slash commands"
```

---

### Task 13: /ask Command

**Files:**
- Create: `lilwman/bot/commands/ask.py`
- Modify: `tests/bot/test_commands.py` (append /ask tests)

**Interfaces:**
- Consumes: `LilwmanBot.ask_query: AskQueryUseCase`
- Produces: `/ask question` slash command

- [ ] **Step 1: Add /ask tests to tests/bot/test_commands.py**

Append to the existing file:

```python
# --- /ask ---
from lilwman.bot.commands.ask import AskCog


async def test_ask_sends_llm_answer():
    ask_uc = AsyncMock()
    ask_uc.execute = AsyncMock(return_value="The answer is 42.")
    bot = make_bot(ask_query=ask_uc)

    cog = AskCog(bot)
    interaction = make_interaction()

    await cog.ask.callback(cog, interaction, question="What is the answer?")

    ask_uc.execute.assert_called_once_with("What is the answer?")
    interaction.response.send_message.assert_called_once()
    call_str = str(interaction.response.send_message.call_args)
    assert "42" in call_str


async def test_ask_sends_not_found_message():
    ask_uc = AsyncMock()
    ask_uc.execute = AsyncMock(return_value="Nothing in the wiki about that.")
    bot = make_bot(ask_query=ask_uc)

    cog = AskCog(bot)
    interaction = make_interaction()

    await cog.ask.callback(cog, interaction, question="unknown topic")

    call_str = str(interaction.response.send_message.call_args)
    assert "nothing" in call_str.lower() or "wiki" in call_str.lower()
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/bot/test_commands.py::test_ask_sends_llm_answer tests/bot/test_commands.py::test_ask_sends_not_found_message -v
```

Expected: `ImportError`

- [ ] **Step 3: Create lilwman/bot/commands/ask.py**

```python
import discord
from discord import app_commands
from discord.ext import commands


class AskCog(commands.Cog):
    def __init__(self, bot) -> None:
        self.bot = bot

    @app_commands.command(name="ask", description="Ask a question answered from the wiki")
    @app_commands.describe(question="Your question")
    async def ask(self, interaction: discord.Interaction, question: str) -> None:
        await interaction.response.defer()
        answer = await self.bot.ask_query.execute(question)
        await interaction.followup.send(f"**Q: {question}**\n\n{answer}")
```

- [ ] **Step 4: Run all tests to verify they pass**

```bash
uv run pytest -v
```

Expected: all tests pass.

- [ ] **Step 5: Run coverage check**

```bash
uv run pytest --cov=lilwman --cov-report=term-missing
```

Expected: application + infrastructure coverage ≥ 80%.

- [ ] **Step 6: Commit**

```bash
git add lilwman/bot/commands/ask.py tests/bot/test_commands.py
git commit -m "feat: /ask slash command with RAG flow"
```

---

## Self-Review Checklist

- [x] **Spec coverage:**
  - Domain entities + ports ✓ (Task 3)
  - SQLite schema: entries, tags, entries_fts ✓ (Task 4)
  - FTS5 standalone table, app-layer managed ✓ (Task 5)
  - StoreEntry use case ✓ (Task 6)
  - SearchEntries use case ✓ (Task 7)
  - DeleteEntry use case ✓ (Task 6)
  - ListByTag use case ✓ (Task 6)
  - AskQuery / RAG use case ✓ (Task 9)
  - Ollama adapter ✓ (Task 8)
  - `/store`, `/search`, `/delete`, `/tag`, `/ask` commands ✓ (Tasks 11–13)
  - Paginated search results (5 per page) ✓ (Task 12 SearchPaginator)
  - Admin can delete any entry ✓ (Task 12)
  - pydantic-settings config ✓ (Task 2)
  - flake.nix devShell ✓ (Task 1)
  - process-compose.yaml ✓ (Task 1)
  - Makefile with deploy target ✓ (Task 1)
  - .env.example ✓ (Task 1)
  - 80%+ test coverage ✓ (Task 13 final check)

- [x] **Type consistency:** `EntryRepository` port methods match repository implementation match use case calls match bot command calls throughout all tasks.

- [x] **No placeholders:** All steps contain complete code.
