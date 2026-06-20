# Test Coverage & Clean Architecture Audit

**Date:** 2026-06-20  
**Scope:** Identify and fill test gaps; verify and enforce strict clean architecture boundaries.

---

## Goal

Two parallel tracks in one pass:
1. Find uncovered lines via pytest-cov, write missing tests to reach ≥85% coverage on non-migration code.
2. Scan all imports per layer against the clean arch contract; fix any violations.

---

## Clean Architecture Contract

```
domain/         → stdlib only
application/    → domain + stdlib only
infrastructure/ → domain + stdlib + sqlalchemy/aiosqlite/ollama
bot/            → application + stdlib + discord
__main__.py     → exempt (composition root)
config.py       → exempt (pydantic-settings only)
```

### Scan method

```bash
grep -r "^import\|^from" lilwman/domain/
grep -r "^import\|^from" lilwman/application/
grep -r "^import\|^from" lilwman/infrastructure/
grep -r "^import\|^from" lilwman/bot/
```

Flag any import that crosses layer boundary. Common violations to watch for:

- `application/` importing `sqlalchemy` types directly
- `application/` importing `discord` for type hints
- `domain/` importing `pydantic` or `sqlalchemy`
- `bot/` calling `session_factory` or `repo` directly (bypassing use cases)
- Use cases returning SQLAlchemy model objects instead of domain `Entry` entities

### Fix strategy

Violation found → move logic to correct layer or replace with domain type.  
No violation → document as confirmed clean.

---

## Predicted Test Gaps

| Area | Gap |
|------|-----|
| `config.py` | No tests — Settings validation, env var loading, defaults |
| `bot/bot.py` | `on_ready`, `setup_hook` cog loading untested |
| `domain/entities.py` | Only 2 tests — missing edge cases (empty tags, timestamp defaults) |
| `infrastructure/repository.py` | FTS5 with reserved-word-only query, special chars, empty string, get-nonexistent-id |
| `application/ask_query.py` | LLM exception path, stopword-only query returning zero results |
| `application/delete_entry.py` | Delete non-existent ID |
| `application/search_entries.py` | Exactly-20 result boundary, empty result |
| `bot/commands/search.py` | SearchPaginator single-page (no nav buttons), last-page boundary |
| `infrastructure/llm/ollama.py` | Connection refused / timeout path |
| `infrastructure/db/session.py` | `init_db` idempotency (run twice, no error) |

Exact uncovered lines confirmed by running:

```bash
pytest --cov=lilwman --cov-report=term-missing
```

---

## Implementation Sequence

1. Run coverage report — capture exact uncovered lines per file
2. Run import scan — grep imports per layer, flag violations
3. Fix arch violations first — clean boundaries before writing tests
4. Write missing tests — ordered: domain → application → infrastructure → bot
5. Re-run coverage — confirm ≥85% on non-migration code
6. Commit — separate commit per concern (arch fixes vs new tests)

---

## Test Style Rules

Match existing project patterns:

- `pytest-asyncio` auto mode — no `@pytest.mark.asyncio` decorator needed
- Application tests → real in-memory SQLite (no mocks)
- Bot tests → mock use cases only, no Discord connection
- Infrastructure tests → real SQLite on `tmp_path`
- LLM tests → mock HTTP client
- Coverage omit: `db/migrations` (already configured in pyproject.toml)
