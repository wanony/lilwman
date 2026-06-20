# Test Coverage & Clean Architecture Audit Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fill test gaps to reach ≥85% coverage on non-migration code and verify all clean architecture layer boundaries are clean.

**Architecture:** Two parallel concerns — test coverage (find and fill uncovered lines per layer) and clean arch (scan imports per layer against contract, fix any violations). Fix arch first so tests aren't written against broken layering.

**Tech Stack:** Python 3.11+, pytest, pytest-asyncio (auto mode), pytest-cov, discord.py, SQLAlchemy async, aiosqlite, pydantic-settings, ollama, uv

## Global Constraints

- pytest-asyncio auto mode: no `@pytest.mark.asyncio` decorator on any test
- Application tests: real in-memory SQLite — never mock the DB
- Bot tests: mock use cases via `AsyncMock`/`MagicMock` — no Discord connection
- Infrastructure tests: real SQLite on `tmp_path`
- LLM tests: mock `ollama.AsyncClient` via `unittest.mock.patch`
- Coverage omit: `db/migrations` (already configured in pyproject.toml)
- All tags stored lowercase in DB; `repo.list_by_tag` calls `tag.lower()` before query
- Run all tests with: `uv run pytest --cov=lilwman --cov-report=term-missing`

---

### Task 1: Run Diagnostic — Coverage and Import Scan

**Files:**
- No changes

**Interfaces:**
- Produces: baseline coverage report + confirmed list of arch violations (if any)

- [ ] **Step 1: Run coverage report**

```bash
uv run pytest --cov=lilwman --cov-report=term-missing 2>&1 | tee /tmp/coverage-baseline.txt
cat /tmp/coverage-baseline.txt
```

Expected: all existing tests pass; report shows uncovered lines per file.

- [ ] **Step 2: Scan domain layer imports**

```bash
grep -rn "^import\|^from" lilwman/domain/
```

Expected: only `abc`, `dataclasses`, `datetime` — no sqlalchemy, discord, ollama, pydantic.

- [ ] **Step 3: Scan application layer imports**

```bash
grep -rn "^import\|^from" lilwman/application/
```

Expected: only `lilwman.domain.*` and stdlib — no sqlalchemy, discord, ollama.

- [ ] **Step 4: Scan infrastructure layer imports**

```bash
grep -rn "^import\|^from" lilwman/infrastructure/
```

Expected: `lilwman.domain.*`, `sqlalchemy`, `aiosqlite`, `ollama`, stdlib — no discord.

- [ ] **Step 5: Scan bot layer imports**

```bash
grep -rn "^import\|^from" lilwman/bot/
```

Expected: `lilwman.application.*`, `lilwman.domain.entities` (for type hints), `discord` — no sqlalchemy, ollama, session_factory.

- [ ] **Step 6: Note findings**

Record any line in the coverage report showing `Miss` and any import that crosses layer boundaries. Proceed to Task 2.

---

### Task 2: Fix Import Ordering in repository.py

**Files:**
- Modify: `lilwman/infrastructure/db/repository.py`

**Interfaces:**
- Consumes: nothing from other tasks
- Produces: PEP8-compliant import ordering; no logic changes

**Context:** `repository.py` currently places `from sqlalchemy import select, text` and other imports mid-file (after the `_sanitize_fts_query` function definition). PEP8 requires all imports at the top. This is not a clean arch violation but is a code quality issue.

- [ ] **Step 1: Write a test to confirm existing behaviour is unchanged after the refactor**

Run the existing infrastructure tests to get a passing baseline:

```bash
uv run pytest tests/infrastructure/test_repository.py -v
```

Expected: all 9 tests pass.

- [ ] **Step 2: Move imports to the top of repository.py**

Replace the current content of `lilwman/infrastructure/db/repository.py` with the imports reordered to the top:

```python
import re
from datetime import datetime, timezone

from sqlalchemy import select, text
from sqlalchemy.orm import selectinload

from lilwman.domain.entities import Entry
from lilwman.domain.ports import EntryRepository
from .models import EntryModel, TagModel

_FTS5_RESERVED = frozenset({"and", "or", "not"})


def _sanitize_fts_query(query: str) -> str:
    # Strip FTS5 special chars
    cleaned = re.sub(r'[^\w\s]', ' ', query)
    # Filter reserved words and empty tokens
    tokens = [t for t in cleaned.split() if t.lower() not in _FTS5_RESERVED]
    return ' '.join(tokens)


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
        clean_tags = [t.strip().lower() for t in tags if t.strip()]
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
        fts_query = _sanitize_fts_query(query)
        if not fts_query:
            return []
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
                    {"q": fts_query, "lim": limit},
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
                .where(TagModel.name == tag.lower())
                .order_by(EntryModel.created_at.desc())
                .limit(10)
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

- [ ] **Step 3: Run tests to confirm nothing broke**

```bash
uv run pytest tests/infrastructure/test_repository.py -v
```

Expected: all 9 tests pass.

- [ ] **Step 4: Commit**

```bash
git add lilwman/infrastructure/db/repository.py
git commit -m "refactor: move repository imports to top of file (PEP8)"
```

---

### Task 3: Add _sanitize_fts_query Unit Tests and Repository Edge Cases

**Files:**
- Modify: `tests/infrastructure/test_repository.py`

**Interfaces:**
- Consumes: `SQLAlchemyEntryRepository` from Task 2, `_sanitize_fts_query` from `lilwman.infrastructure.db.repository`
- Produces: coverage for `_sanitize_fts_query`, `search` empty/reserved-word paths, `delete` non-existent path, `list_by_tag` uppercase input

- [ ] **Step 1: Write the failing tests**

Append to `tests/infrastructure/test_repository.py`:

```python
from lilwman.infrastructure.db.repository import _sanitize_fts_query


# --- _sanitize_fts_query unit tests ---

def test_sanitize_removes_reserved_words():
    assert _sanitize_fts_query("and or not") == ""


def test_sanitize_removes_special_chars():
    assert _sanitize_fts_query("python!!!") == "python"


def test_sanitize_empty_string_returns_empty():
    assert _sanitize_fts_query("") == ""


def test_sanitize_preserves_normal_words():
    assert _sanitize_fts_query("python nix") == "python nix"


def test_sanitize_mixed_reserved_and_normal():
    assert _sanitize_fts_query("and python not") == "python"


# --- repository edge cases ---

async def test_search_empty_query_returns_empty(repo):
    await repo.save(content="something", tags=[], author_id="1", author_name="a")
    results = await repo.search("")
    assert results == []


async def test_search_reserved_words_only_returns_empty(repo):
    await repo.save(content="and or not", tags=[], author_id="1", author_name="a")
    results = await repo.search("and or not")
    assert results == []


async def test_search_special_chars_sanitized(repo):
    await repo.save(content="python is great", tags=[], author_id="1", author_name="a")
    results = await repo.search("python!!!")
    assert len(results) == 1
    assert results[0].content == "python is great"


async def test_delete_nonexistent_entry_returns_false(repo):
    result = await repo.delete(9999, author_id="111", is_admin=True)
    assert result is False


async def test_list_by_tag_uppercase_input_matches_lowercase_stored(repo):
    await repo.save(content="python entry", tags=["python"], author_id="1", author_name="a")
    results = await repo.list_by_tag("PYTHON")
    assert len(results) == 1
    assert results[0].content == "python entry"
```

- [ ] **Step 2: Run to verify they fail correctly**

```bash
uv run pytest tests/infrastructure/test_repository.py -v -k "sanitize or empty_query or reserved_words or special_chars or nonexistent or uppercase"
```

Expected: `test_sanitize_*` and `test_search_*` and `test_delete_nonexistent*` and `test_list_by_tag_uppercase*` — some pass (sanitize functions already exist), confirm all run and the new repo tests pass too since the logic already handles these cases.

- [ ] **Step 3: Run full infrastructure test suite**

```bash
uv run pytest tests/infrastructure/test_repository.py -v
```

Expected: all tests pass (14 total now).

- [ ] **Step 4: Commit**

```bash
git add tests/infrastructure/test_repository.py
git commit -m "test: add _sanitize_fts_query unit tests and repository edge cases"
```

---

### Task 4: Add Session Tests

**Files:**
- Create: `tests/infrastructure/test_session.py`

**Interfaces:**
- Consumes: `create_engine`, `create_session_factory`, `init_db` from `lilwman.infrastructure.db.session`
- Produces: coverage for session.py `create_engine`, `init_db` (including idempotency), `create_session_factory`

- [ ] **Step 1: Write the failing tests**

Create `tests/infrastructure/test_session.py`:

```python
from sqlalchemy import text

from lilwman.infrastructure.db.session import create_engine, create_session_factory, init_db


async def test_create_engine_returns_async_engine(tmp_path):
    db_path = str(tmp_path / "test.db")
    engine = create_engine(db_path)
    assert engine is not None
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


async def test_create_session_factory_returns_working_session(tmp_path):
    db_path = str(tmp_path / "test.db")
    engine = create_engine(db_path)
    await init_db(engine)
    factory = create_session_factory(engine)

    async with factory() as session:
        assert session is not None

    await engine.dispose()
```

- [ ] **Step 2: Run to verify tests pass**

```bash
uv run pytest tests/infrastructure/test_session.py -v
```

Expected: all 5 tests pass.

- [ ] **Step 3: Commit**

```bash
git add tests/infrastructure/test_session.py
git commit -m "test: add session.py coverage (create_engine, init_db idempotency, session factory)"
```

---

### Task 5: Add OllamaLLM Error Propagation Test

**Files:**
- Modify: `tests/infrastructure/test_ollama.py`

**Interfaces:**
- Consumes: `OllamaLLM` from `lilwman.infrastructure.llm.ollama`
- Produces: coverage for the exception-propagation path in `generate`

- [ ] **Step 1: Write the failing test**

Append to `tests/infrastructure/test_ollama.py`:

```python
async def test_generate_propagates_exception_from_client():
    with patch(
        "lilwman.infrastructure.llm.ollama.ollama.AsyncClient"
    ) as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.generate = AsyncMock(
            side_effect=RuntimeError("connection refused")
        )
        mock_client_cls.return_value = mock_client

        llm = OllamaLLM(host="http://localhost:11434", model="qwen2.5:1.5b")

        with pytest.raises(RuntimeError, match="connection refused"):
            await llm.generate("test prompt")
```

- [ ] **Step 2: Run to verify it passes**

```bash
uv run pytest tests/infrastructure/test_ollama.py -v
```

Expected: all 3 tests pass.

- [ ] **Step 3: Commit**

```bash
git add tests/infrastructure/test_ollama.py
git commit -m "test: add OllamaLLM exception propagation test"
```

---

### Task 6: Add Config Tests

**Files:**
- Create: `tests/test_config.py`

**Interfaces:**
- Consumes: `Settings` from `lilwman.config`
- Produces: coverage for `config.py` — required fields, default values, custom overrides

**Note:** pydantic-settings v2 accepts field values as constructor kwargs, which take precedence over env vars and `.env` files. This is the safest way to test `Settings` without environment contamination.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_config.py`:

```python
import pytest
from pydantic import ValidationError

from lilwman.config import Settings


def test_settings_required_fields_accepted():
    s = Settings(discord_token="my-token", discord_guild_id=12345)
    assert s.discord_token == "my-token"
    assert s.discord_guild_id == 12345


def test_settings_ollama_host_default():
    s = Settings(discord_token="t", discord_guild_id=1)
    assert s.ollama_host == "http://localhost:11434"


def test_settings_ollama_model_default():
    s = Settings(discord_token="t", discord_guild_id=1)
    assert s.ollama_model == "qwen2.5:1.5b"


def test_settings_db_path_default():
    s = Settings(discord_token="t", discord_guild_id=1)
    assert s.db_path == "data/lilwman.db"


def test_settings_custom_ollama_host():
    s = Settings(
        discord_token="t",
        discord_guild_id=1,
        ollama_host="http://remote:11434",
    )
    assert s.ollama_host == "http://remote:11434"


def test_settings_custom_ollama_model():
    s = Settings(
        discord_token="t",
        discord_guild_id=1,
        ollama_model="llama3.2:3b",
    )
    assert s.ollama_model == "llama3.2:3b"


def test_settings_custom_db_path():
    s = Settings(
        discord_token="t",
        discord_guild_id=1,
        db_path="/var/data/bot.db",
    )
    assert s.db_path == "/var/data/bot.db"


def test_settings_guild_id_is_int():
    s = Settings(discord_token="t", discord_guild_id=999888777)
    assert isinstance(s.discord_guild_id, int)
    assert s.discord_guild_id == 999888777
```

- [ ] **Step 2: Run to verify tests pass**

```bash
uv run pytest tests/test_config.py -v
```

Expected: all 8 tests pass.

- [ ] **Step 3: Commit**

```bash
git add tests/test_config.py
git commit -m "test: add config Settings coverage (defaults, required fields, custom values)"
```

---

### Task 7: Add Application Layer Gap Tests

**Files:**
- Modify: `tests/application/test_search_entries.py`
- Modify: `tests/application/test_store_entry.py`
- Modify: `tests/application/test_list_by_tag.py`
- Modify: `tests/application/test_ask_query.py`

**Interfaces:**
- Consumes: `StoreEntryUseCase`, `SearchEntriesUseCase`, `ListByTagUseCase`, `AskQueryUseCase`, `DeleteEntryUseCase` from `lilwman.application.*`; `repo` fixture from `tests/application/conftest.py`
- Produces: coverage for search limit boundary, tag whitespace stripping, list_by_tag case-insensitivity, ask with all-stopword question, ask with newlines in question

- [ ] **Step 1: Add search limit boundary test to test_search_entries.py**

Append to `tests/application/test_search_entries.py`:

```python
async def test_search_respects_limit_of_20(store, search):
    for i in range(21):
        await store.execute(f"python entry number {i}", ["python"], str(i), f"user{i}")
    results = await search.execute("python")
    assert len(results) == 20


async def test_search_empty_query_returns_empty(search):
    results = await search.execute("")
    assert results == []
```

- [ ] **Step 2: Add tag whitespace stripping test to test_store_entry.py**

Append to `tests/application/test_store_entry.py`:

```python
async def test_store_entry_strips_whitespace_from_tags(use_case):
    entry = await use_case.execute(
        content="test content",
        tags=["  python  ", " nix "],
        author_id="1",
        author_name="alice",
    )
    assert entry.tags == ["python", "nix"]


async def test_store_entry_lowercases_tags(use_case):
    entry = await use_case.execute(
        content="test content",
        tags=["Python", "NIX"],
        author_id="1",
        author_name="alice",
    )
    assert entry.tags == ["python", "nix"]


async def test_store_entry_filters_blank_tags(use_case):
    entry = await use_case.execute(
        content="test content",
        tags=["python", "", "  "],
        author_id="1",
        author_name="alice",
    )
    assert entry.tags == ["python"]
```

- [ ] **Step 3: Add case-insensitive list_by_tag test to test_list_by_tag.py**

Append to `tests/application/test_list_by_tag.py`:

```python
async def test_list_by_tag_case_insensitive(store, list_tag):
    await store.execute("python entry", ["Python"], "1", "a")
    results = await list_tag.execute("PYTHON")
    assert len(results) == 1
    assert results[0].content == "python entry"
```

- [ ] **Step 4: Add ask_query gap tests to test_ask_query.py**

Append to `tests/application/test_ask_query.py`:

```python
async def test_ask_with_all_stopwords_returns_not_found(ask, mock_llm):
    # "what is the" are all stopwords; _keywords returns ""; falls back to full
    # question "what is the" which won't match anything in an empty repo
    answer = await ask.execute("what is the")
    assert answer == "Nothing in the wiki about that."
    mock_llm.generate.assert_not_called()


async def test_ask_strips_newlines_from_question_in_prompt(store, ask, mock_llm):
    await store.execute("security topic details", ["security"], "1", "a")
    await ask.execute("security\ninfo")
    prompt = mock_llm.generate.call_args[0][0]
    # The "Question:" line in the prompt must not contain a literal newline
    question_section = prompt.split("Question:")[-1]
    assert "\n" not in question_section.rstrip("\n").split("\n")[0]


async def test_ask_keywords_filters_stopwords(store, ask, mock_llm):
    await store.execute("python decorators guide", ["python"], "1", "a")
    # "what is python" → keywords = "python" → finds match
    answer = await ask.execute("what is python")
    assert answer == "Paris is the capital of France."  # mock_llm returns this
    mock_llm.generate.assert_called_once()
```

- [ ] **Step 5: Run all application tests**

```bash
uv run pytest tests/application/ -v
```

Expected: all tests pass (previous 15 + 8 new = 23 total).

- [ ] **Step 6: Commit**

```bash
git add tests/application/test_search_entries.py tests/application/test_store_entry.py tests/application/test_list_by_tag.py tests/application/test_ask_query.py
git commit -m "test: add application layer gap tests (search limit, tag normalisation, ask edge cases)"
```

---

### Task 8: Add Bot Layer Tests

**Files:**
- Create: `tests/bot/test_bot.py`
- Modify: `tests/bot/test_commands.py`

**Interfaces:**
- Consumes: `LilwmanBot` from `lilwman.bot.bot`; `SearchPaginator` from `lilwman.bot.commands.search`; `TagCog` from `lilwman.bot.commands.tag`; helper factories `make_bot`, `make_interaction`, `make_entry` already defined in `tests/bot/test_commands.py`
- Produces: coverage for `on_app_command_error` (both branches), `SearchPaginator` pagination logic, `TagCog` overflow branch

- [ ] **Step 1: Write bot error handler tests**

Create `tests/bot/test_bot.py`:

```python
from unittest.mock import AsyncMock, MagicMock
import discord
from discord import app_commands

from lilwman.bot.bot import LilwmanBot


def make_bot_instance():
    return LilwmanBot(
        guild_id=1,
        store_entry=AsyncMock(),
        search_entries=AsyncMock(),
        delete_entry=AsyncMock(),
        list_by_tag=AsyncMock(),
        ask_query=AsyncMock(),
    )


async def test_error_handler_sends_message_when_response_not_done():
    bot = make_bot_instance()

    interaction = AsyncMock(spec=discord.Interaction)
    interaction.response = AsyncMock()
    interaction.response.is_done = MagicMock(return_value=False)
    interaction.followup = AsyncMock()

    error = app_commands.AppCommandError("test error")
    await bot.on_app_command_error(interaction, error)

    interaction.response.send_message.assert_called_once()
    kwargs = interaction.response.send_message.call_args.kwargs
    assert kwargs.get("ephemeral") is True


async def test_error_handler_uses_followup_when_response_done():
    bot = make_bot_instance()

    interaction = AsyncMock(spec=discord.Interaction)
    interaction.response = AsyncMock()
    interaction.response.is_done = MagicMock(return_value=True)
    interaction.followup = AsyncMock()

    error = app_commands.AppCommandError("test error")
    await bot.on_app_command_error(interaction, error)

    interaction.followup.send.assert_called_once()
    kwargs = interaction.followup.send.call_args.kwargs
    assert kwargs.get("ephemeral") is True


async def test_error_handler_message_text():
    bot = make_bot_instance()

    interaction = AsyncMock(spec=discord.Interaction)
    interaction.response = AsyncMock()
    interaction.response.is_done = MagicMock(return_value=False)
    interaction.followup = AsyncMock()

    error = app_commands.AppCommandError("oops")
    await bot.on_app_command_error(interaction, error)

    call_args = interaction.response.send_message.call_args
    message = call_args.args[0] if call_args.args else call_args.kwargs.get("content", "")
    assert "wrong" in message.lower() or "try again" in message.lower()
```

- [ ] **Step 2: Write SearchPaginator tests**

Append to `tests/bot/test_commands.py`:

```python
# --- SearchPaginator ---
from lilwman.bot.commands.search import SearchPaginator, PER_PAGE


def test_paginator_total_pages_single_page():
    results = [make_entry(id=i) for i in range(1, 4)]  # 3 entries < PER_PAGE(5)
    p = SearchPaginator(results, "q")
    assert p.total_pages == 1


def test_paginator_total_pages_exact_boundary():
    results = [make_entry(id=i) for i in range(1, PER_PAGE + 1)]  # exactly 5
    p = SearchPaginator(results, "q")
    assert p.total_pages == 1


def test_paginator_total_pages_over_boundary():
    results = [make_entry(id=i) for i in range(1, PER_PAGE + 2)]  # 6 entries
    p = SearchPaginator(results, "q")
    assert p.total_pages == 2


def test_paginator_embed_title_includes_query():
    results = [make_entry(id=1)]
    p = SearchPaginator(results, "my search")
    embed = p.make_embed()
    assert "my search" in embed.title


def test_paginator_embed_footer_shows_page_count():
    results = [make_entry(id=i) for i in range(1, 7)]  # 2 pages
    p = SearchPaginator(results, "q")
    embed = p.make_embed()
    assert "1/2" in embed.footer.text


async def test_paginator_prev_button_decrements_page():
    results = [make_entry(id=i) for i in range(1, 7)]  # 2 pages
    p = SearchPaginator(results, "q")
    p.page = 1

    interaction = AsyncMock()
    interaction.response = AsyncMock()

    await p.prev.callback(p, interaction, MagicMock())

    assert p.page == 0
    interaction.response.edit_message.assert_called_once()


async def test_paginator_prev_button_clamped_at_zero():
    results = [make_entry(id=i) for i in range(1, 4)]
    p = SearchPaginator(results, "q")
    p.page = 0

    interaction = AsyncMock()
    interaction.response = AsyncMock()

    await p.prev.callback(p, interaction, MagicMock())

    assert p.page == 0


async def test_paginator_next_button_increments_page():
    results = [make_entry(id=i) for i in range(1, 7)]  # 2 pages
    p = SearchPaginator(results, "q")
    p.page = 0

    interaction = AsyncMock()
    interaction.response = AsyncMock()

    await p.next.callback(p, interaction, MagicMock())

    assert p.page == 1
    interaction.response.edit_message.assert_called_once()


async def test_paginator_next_button_clamped_at_last_page():
    results = [make_entry(id=i) for i in range(1, 7)]  # 2 pages (0, 1)
    p = SearchPaginator(results, "q")
    p.page = 1  # already on last page

    interaction = AsyncMock()
    interaction.response = AsyncMock()

    await p.next.callback(p, interaction, MagicMock())

    assert p.page == 1


# --- TagCog overflow ---
from lilwman.bot.commands.tag import TagCog


async def test_tag_more_than_10_entries_shows_footer():
    entries = [make_entry(id=i) for i in range(1, 13)]  # 12 entries
    list_uc = AsyncMock()
    list_uc.execute = AsyncMock(return_value=entries)
    bot = make_bot(list_by_tag=list_uc)

    cog = TagCog(bot)
    interaction = make_interaction()

    await cog.tag.callback(cog, interaction, name="popular")

    kwargs = interaction.response.send_message.call_args.kwargs
    embed = kwargs["embed"]
    assert len(embed.fields) == 10
    assert "12" in embed.footer.text
```

- [ ] **Step 3: Run bot tests**

```bash
uv run pytest tests/bot/ -v
```

Expected: all tests pass (14 existing + 3 in test_bot.py + 11 new in test_commands.py = 28 total).

- [ ] **Step 4: Commit**

```bash
git add tests/bot/test_bot.py tests/bot/test_commands.py
git commit -m "test: add bot error handler, SearchPaginator pagination, and TagCog overflow tests"
```

---

### Task 9: Verify Final Coverage

**Files:**
- No changes

**Interfaces:**
- Consumes: all tests from Tasks 1–8
- Produces: confirmed coverage ≥85% across non-migration code

- [ ] **Step 1: Run full test suite with coverage**

```bash
uv run pytest --cov=lilwman --cov-report=term-missing -v 2>&1 | tee /tmp/coverage-final.txt
cat /tmp/coverage-final.txt
```

Expected: all tests pass, overall coverage ≥85% (excluding `db/migrations`).

- [ ] **Step 2: Check for any remaining uncovered lines**

Scan the term-missing output for any `Miss` lines outside of `db/migrations`, `__main__.py`, and `config.py` model_config internals. If any non-trivial branch is uncovered, add a targeted test following the same pattern as Tasks 3–8.

- [ ] **Step 3: Compare to baseline**

```bash
diff /tmp/coverage-baseline.txt /tmp/coverage-final.txt | grep "^[<>]" | head -40
```

Expected: coverage percentage increased across all layers.

- [ ] **Step 4: Final commit**

```bash
git add -A
git commit -m "test: verify ≥85% coverage across all non-migration layers"
```
