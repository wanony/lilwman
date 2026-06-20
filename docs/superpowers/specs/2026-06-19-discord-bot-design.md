# lilwman Discord Bot — Design Spec

**Date:** 2026-06-19  
**Status:** Approved

---

## Overview

Single-server Discord bot. Shared free-form wiki: any member can store tagged entries, search them, and ask questions answered via RAG over the stored content. Local LLM (Qwen2.5:1.5b via Ollama) synthesizes answers from FTS5 search results. Hosted on gigi (ThinkPad X220, NixOS), developed locally on Mac, deployed via rsync.

---

## Stack

| Concern | Choice |
|---|---|
| Language | Python 3.11+ |
| Discord | `discord.py` 2.x (`app_commands` for slash commands) |
| ORM | `SQLAlchemy` 2.x async |
| DB driver | `aiosqlite` |
| Migrations | `alembic` |
| Config | `pydantic-settings` (reads `.env`) |
| LLM runtime | Ollama (`qwen2.5:1.5b`) |
| LLM client | `ollama` Python client |
| Testing | `pytest` + `pytest-asyncio` + `pytest-cov` |
| Packaging | `uv` |

---

## Architecture

Clean architecture. Dependency rule: `bot` → `application` → `domain`. Infrastructure implements domain ports. Domain has zero framework dependencies.

```
lilwman/
├── domain/
│   ├── entities.py          # Entry, Tag dataclasses
│   └── ports.py             # Abstract repository interfaces (ABCs)
├── infrastructure/
│   ├── db/
│   │   ├── models.py        # SQLAlchemy ORM models
│   │   ├── repositories.py  # Concrete port implementations
│   │   └── migrations/      # Alembic migrations
│   └── llm/
│       └── ollama.py        # Ollama adapter (implements LLMPort)
├── application/
│   ├── store_entry.py       # Use case: store a wiki entry
│   ├── search_entries.py    # Use case: FTS5 keyword search
│   └── ask_query.py         # Use case: RAG flow
├── bot/
│   ├── bot.py               # discord.py Client + command tree setup
│   └── commands/
│       ├── store.py
│       ├── search.py
│       ├── ask.py
│       ├── delete.py
│       └── tag.py
├── config.py                # pydantic-settings
└── main.py                  # Composition root
```

---

## Data Model

### SQLite tables

**entries**
```
id          INTEGER PRIMARY KEY AUTOINCREMENT
content     TEXT NOT NULL
author_id   TEXT NOT NULL        -- Discord user snowflake
author_name TEXT NOT NULL        -- snapshot at creation time
created_at  DATETIME NOT NULL
updated_at  DATETIME NOT NULL
```

**tags**
```
id          INTEGER PRIMARY KEY AUTOINCREMENT
entry_id    INTEGER NOT NULL REFERENCES entries(id) ON DELETE CASCADE
name        TEXT NOT NULL
```

**entries_fts** (FTS5 virtual table — standalone, app-layer managed)
```sql
CREATE VIRTUAL TABLE entries_fts USING fts5(
    entry_id UNINDEXED,
    content,
    tags
);
```
Not an external content table — app layer explicitly inserts/updates/deletes rows in `entries_fts` in the same transaction as `entries`. `tags` column is a space-separated string of all tag names for that entry. `entry_id` is stored unindexed for joining back to `entries`.

### Domain entities

```python
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

---

## Commands

| Command | Args | Behavior |
|---|---|---|
| `/store` | `content: str`, `tags: str` (optional, comma-sep) | Save entry, reply with ID |
| `/search` | `query: str` | FTS5 keyword search, paginated embed (5 per page) |
| `/ask` | `question: str` | RAG flow → public synthesized answer |
| `/delete` | `id: int` | Delete own entry; server admin can delete any |
| `/tag` | `name: str` | List all entries with given tag |

All commands are slash commands (`app_commands`). No prefix commands.

---

## RAG Flow (`/ask`)

```
1. FTS5 search on question terms → top 5 entries ranked by relevance
2. If no results → reply "Nothing in the wiki about that."
3. Build prompt:
   - system: "Answer using only the provided wiki entries. Be concise."
   - context: entries formatted as numbered snippets with tags
   - user: question
4. POST to Ollama /api/generate (non-streaming for simplicity)
5. Reply publicly in channel
```

### LLM port (abstract)

```python
class LLMPort(ABC):
    async def generate(self, prompt: str) -> str: ...
```

Ollama adapter implements this. Swapping to Claude Haiku = new class, nothing else changes.

---

## Testing

| Layer | Approach |
|---|---|
| Domain | Plain `pytest`, no async |
| Application | `pytest-asyncio`, real in-memory SQLite (no mocks) |
| Infrastructure | `pytest-asyncio`, real SQLite via `tmp_path` fixture |
| Bot commands | Mock application layer, no Discord connection |
| LLM adapter | Mock HTTP responses, no real Ollama in CI |

No DB mocking in application tests — real SQLite in-memory is fast and catches real SQL bugs.

Target: 80%+ coverage on application + infrastructure layers.

```
tests/
├── domain/
├── application/
├── infrastructure/
└── bot/
```

---

## Nix & Deployment

### Local dev (Mac)

`flake.nix` provides a `devShell` with:
- `uv`, `python311`, `ollama`, `process-compose`

`process-compose.yaml` manages both processes:
```yaml
processes:
  ollama:
    command: ollama serve
    readiness_probe:
      http_get: { path: /, port: 11434 }
  bot:
    command: uv run python -m lilwman
    depends_on:
      ollama: { condition: process_healthy }
```

`nix develop` → `process-compose up` to run everything locally.

### Gigi (NixOS, production)

`uv`, `ollama`, `process-compose` added to `environment.systemPackages` on gigi. No `nix develop` needed in the service.

NixOS systemd service (`/etc/nixos/modules/lilwman.nix`):
```nix
systemd.services.lilwman = {
  description = "lilwman discord bot";
  wantedBy = [ "multi-user.target" ];
  after = [ "network.target" ];
  serviceConfig = {
    WorkingDirectory = "/opt/lilwman";
    ExecStart = "${pkgs.process-compose}/bin/process-compose up";
    EnvironmentFile = "/opt/lilwman/.env";
    Restart = "on-failure";
    RestartSec = "5s";
  };
};
```

### Deploy workflow

```makefile
deploy:
    rsync -av --exclude='.venv' --exclude='.env' --exclude='__pycache__' \
        . gigi:/opt/lilwman/
    ssh gigi "cd /opt/lilwman && uv sync && systemctl restart lilwman"
```

### Secrets

`.env` on gigi, never committed:
```
DISCORD_TOKEN=...
DISCORD_GUILD_ID=...
OLLAMA_HOST=http://localhost:11434
OLLAMA_MODEL=qwen2.5:1.5b
DB_PATH=/opt/lilwman/data/lilwman.db
```

---

## LLM Model

Default: `qwen2.5:1.5b` via Ollama.
- ~900MB on disk, ~1.5GB RAM
- ~4 tok/s on X220 CPU
- Adequate for RAG synthesis (model reads pre-filtered snippets, not full DB)

Fallback: `qwen2.5:0.5b` if RAM constrained. Cloud swap (Claude Haiku) requires only replacing the `LLMPort` implementation.
