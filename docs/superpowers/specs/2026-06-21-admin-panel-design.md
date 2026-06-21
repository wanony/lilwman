# Admin Panel Design

**Date:** 2026-06-21
**Scope:** Discord `/admin` command group + FastAPI web panel for content moderation, stats, feed management, and per-guild configuration.

---

## Architecture

Two subsystems share the same use cases via dependency injection:

1. **Discord commands** — `/admin` app_commands group in `bot/commands/admin.py`
2. **Web panel** — FastAPI app in `infrastructure/web/`, served alongside the bot via `asyncio.gather()`

```
domain/
  admin_entities.py          — BotStats dataclass, GuildConfig dataclass

application/
  get_stats.py               — GetStatsUseCase
  get_entry.py               — GetEntryUseCase → Entry | None (fetch single entry by id)
  edit_entry.py              — EditEntryUseCase (admin-only)
  list_by_author.py          — ListByAuthorUseCase
  list_all_entries.py        — ListAllEntriesUseCase → paginated list for web browser
  purge_by_author.py         — PurgeByAuthorUseCase → int (deleted count)
  purge_by_tag.py            — PurgeByTagUseCase → int (deleted count)
  get_guild_config.py        — GetGuildConfigUseCase
  set_guild_config.py        — SetGuildConfigUseCase

infrastructure/
  db/
    guild_config_models.py   — GuildConfigModel ORM (table: guild_configs)
    guild_config_repo.py     — SQLAlchemyGuildConfigRepository
    migrations/0003_admin.py — creates guild_configs, adds guild_id to feed_subscriptions
  web/
    app.py                   — FastAPI app factory (use cases injected as args)
    auth.py                  — Discord OAuth flow + itsdangerous signed-cookie session
    routes/
      dashboard.py           — GET /
      entries.py             — GET/POST /entries and sub-routes
      feeds.py               — GET /feeds, POST /feeds/{id}/delete
      config.py              — GET/POST /config
    templates/
      base.html              — dark sidebar nav + Tailwind CDN
      login.html
      dashboard.html
      entries.html
      entry_edit.html
      feeds.html
      config.html

bot/
  commands/admin.py          — AdminCog: /admin group

config.py                    — 6 new fields (see Configuration section)
__main__.py                  — asyncio.gather(bot.start(), uvicorn.Server(...).serve())
```

**New dependencies:** `fastapi`, `uvicorn`, `jinja2`, `itsdangerous`.

**Clean arch contract (unchanged):**
- `domain/` → stdlib only
- `application/` → domain + stdlib only
- `infrastructure/` → domain + stdlib + sqlalchemy/aiosqlite/aiohttp/feedparser/fastapi/jinja2
- `bot/` → application + stdlib + discord
- `__main__.py` → exempt (composition root)
- `config.py` → exempt (pydantic-settings only)

---

## Data Model

### New table: `guild_configs`

| Column | Type | Notes |
|---|---|---|
| id | INTEGER PK | |
| guild_id | TEXT UNIQUE | Discord guild snowflake |
| store_restricted | BOOLEAN | Default False — if True, /store requires administrator |
| created_at | DATETIME | |
| updated_at | DATETIME | |

Upsert on write (`INSERT OR REPLACE`). One row per guild, created on first `/admin config set` or first `/store` invocation.

### Modified table: `feed_subscriptions`

Add `guild_id TEXT NOT NULL DEFAULT ''` column. Migration `0003_admin` adds the column with empty string default for existing rows. `AddFeedUseCase.execute()` gains a `guild_id: str` parameter. `FeedCog.feed_add` (and all feed commands) passes `str(interaction.guild_id)`.

### Domain entities

```python
@dataclass
class BotStats:
    total_entries: int
    entries_this_week: int
    entries_this_month: int
    total_feeds: int
    unique_tags: int
    top_tags: list[tuple[str, int]]     # (tag, count) top 10
    top_authors: list[tuple[str, int]]  # (author_name, count) top 10

@dataclass
class GuildConfig:
    guild_id: str
    store_restricted: bool
    created_at: datetime
    updated_at: datetime
```

---

## Stats

`GetStatsUseCase.execute(guild_id: str) -> BotStats`

All counts filtered to the given guild:
- `total_entries` — `COUNT(*)` from `entries` where `guild_id = ?`
- `entries_this_week` — entries with `created_at >= now - 7 days`
- `entries_this_month` — entries with `created_at >= now - 30 days`
- `total_feeds` — `COUNT(*)` from `feed_subscriptions` where `guild_id = ?`
- `unique_tags` — `COUNT(DISTINCT tag)` from entry tags for that guild
- `top_tags` — top 10 tags by entry count
- `top_authors` — top 10 authors by entry count (using `author_name`)

**Note:** `entries` table currently has no `guild_id` column. Migration `0003_admin` adds `guild_id TEXT NOT NULL DEFAULT ''` to `entries`. `StoreEntryUseCase.execute()` gains a `guild_id: str` parameter. `StoreCog.store` passes `str(interaction.guild_id)`.

Stats exclude rows with empty `guild_id` (pre-migration entries) from guild-scoped counts — acceptable gap.

---

## Discord Commands

`AdminCog` registers `admin = app_commands.Group(name="admin", description="Admin tools")`.

All subcommands check at entry:
```python
if interaction.guild_id is None:
    # DM guard
if not interaction.user.guild_permissions.administrator:
    # permission denied
```

| Command | Args | Behaviour |
|---|---|---|
| `/admin stats` | — | Ephemeral embed: BotStats for current guild |
| `/admin list-user <user>` | user: discord.Member | Paginated embed, 10 entries/page, oldest-first. Reuses SearchPaginator pattern |
| `/admin edit <id> <content> [tags]` | id: int, content: str, tags: str="" | EditEntryUseCase. tags = comma-separated string. Ephemeral confirmation on success |
| `/admin purge user <user>` | user: discord.Member | Ephemeral reply with entry count + ✅ Confirm button. On confirm: PurgeByAuthorUseCase, report count |
| `/admin purge tag <tag>` | tag: str | Same confirmation pattern. PurgeByTagUseCase |
| `/admin config show` | — | Ephemeral embed of current GuildConfig |
| `/admin config set store-restricted <value>` | value: bool | SetGuildConfigUseCase. Ephemeral confirmation |

`purge` is a nested `app_commands.Group`. `config` is a nested `app_commands.Group`.

### Confirmation view

```python
class ConfirmView(discord.ui.View):
    def __init__(self, callback: Callable, timeout: float = 60.0): ...

    @discord.ui.button(label="Confirm", style=discord.ButtonStyle.danger)
    async def confirm(self, interaction, button): ...
    # On timeout: disable button, edit message to "Timed out."
```

### `/store` restriction

`StoreCog.store` checks `GetGuildConfigUseCase.execute(guild_id).store_restricted`. If True and user is not administrator, reply ephemeral "Storing entries is restricted to admins on this server." and return. Config defaults to `store_restricted=False` when no row exists (upsert-on-first-write).

---

## Web Panel

### Running alongside bot

```python
# __main__.py
import uvicorn

async def main():
    web_config = uvicorn.Config(web_app, host="0.0.0.0", port=settings.web_port, log_level="warning")
    server = uvicorn.Server(web_config)
    await asyncio.gather(
        bot.start(settings.discord_token),
        server.serve(),
    )

asyncio.run(main())
```

### Discord OAuth

**Flow:**
1. `GET /login` → redirect to `https://discord.com/oauth2/authorize?client_id=...&redirect_uri=...&scope=identify+guilds&response_type=code`
2. `GET /auth/callback?code=...` → POST to `https://discord.com/api/oauth2/token` (exchange code) → GET `https://discord.com/api/users/@me` + `https://discord.com/api/users/@me/guilds`
3. Filter user's guilds to those where bot is present AND user has `ADMINISTRATOR` permission flag (`0x8`)
4. If none: render login page with error "You are not an administrator in any server this bot is in."
5. If valid: create signed session cookie (`itsdangerous.URLSafeTimedSerializer`, max-age 86400s) containing `{"user_id": ..., "username": ..., "avatar": ...}`
6. Redirect to `/`

**Session dependency:**
```python
async def get_current_user(request: Request) -> SessionUser:
    cookie = request.cookies.get("session")
    if not cookie:
        raise HTTPException(302, headers={"Location": "/login"})
    try:
        data = serializer.loads(cookie, max_age=86400)
    except SignatureExpired:
        raise HTTPException(302, headers={"Location": "/login?error=session_expired"})
    return SessionUser(**data)
```

All routes receive `user: SessionUser = Depends(get_current_user)`.

### Pages

**`GET /` — Dashboard**
Calls `GetStatsUseCase.execute(settings.web_guild_id)`. Renders `dashboard.html`: stat cards (total entries, this week, this month, feeds), top-10 tags bar chart (CSS only, no JS), top-10 authors table.

**`GET /entries?q=&author=&page=1` — Entries browser**
- If `q`: calls `SearchEntriesUseCase.execute(q)` → paginate results
- If `author` (Discord user ID string): calls `ListByAuthorUseCase.execute(author_id)`
- Default: all entries paginated (new `ListAllEntriesUseCase` or extend repository)
- 20 entries per page. Table: id, content (truncated 100 chars), tags, author, date, Edit/Delete buttons

**`GET /entries/{id}/edit` — Edit form**
Form with content textarea + tags input (comma-separated). Populated from `GetEntryUseCase` (existing repo `get_by_id`).

**`POST /entries/{id}/edit` — Save edit**
Calls `EditEntryUseCase.execute(id, content, tags, is_admin=True)`. Redirect to `/entries` with flash "Entry #{id} updated."

**`POST /entries/{id}/delete` — Delete**
Calls `DeleteEntryUseCase.execute(id, author_id="web-admin", is_admin=True)`. Redirect to `/entries` with flash.

**`POST /entries/purge/user` — Purge by user**
Form field `author_id`. Calls `PurgeByAuthorUseCase`. Redirect with flash "Deleted N entries."

**`POST /entries/purge/tag` — Purge by tag**
Form field `tag`. Calls `PurgeByTagUseCase`. Redirect with flash.

**`GET /feeds` — Feed subscriptions**
`FeedRepository.list_all()` (already exists). Table: id, guild_id, channel_id, platform, account, created_at, Delete button.

**`POST /feeds/{id}/delete` — Delete feed**
Calls `repo.delete(feed_id, channel_id=None)` — web context bypasses channel ownership. `FeedRepository.delete` gains an `admin: bool = False` param: if True, skips channel_id check.

**`GET /config` — Guild config**
Current `GuildConfig` rendered as form.

**`POST /config` — Save config**
`SetGuildConfigUseCase.execute(guild_id, store_restricted=...)`. Redirect with flash.

### Flash messages

Signed cookie `flash` (same `itsdangerous` serializer, single-use). Set on redirect, read+cleared on next render. Template renders flash banner in `base.html` if present.

### Styling

`base.html` loads Tailwind CSS via CDN play link. Dark sidebar (`bg-gray-900`) with nav links: Dashboard, Entries, Feeds, Config. Main content area (`bg-gray-100`). Stat cards on dashboard. Responsive table with hover rows. No JS framework — plain HTML form POSTs.

---

## Configuration

Six new fields added to `Settings` in `config.py`:

```python
discord_client_id: str = ""
discord_client_secret: str = ""
web_base_url: str = "http://localhost:8080"   # OAuth redirect base
web_port: int = 8080
web_secret_key: str = ""                       # required; raise at startup if empty
web_guild_id: str = ""                         # guild to show stats for in web panel
```

Startup check in `__main__.py`: if `settings.web_secret_key == ""`, raise `RuntimeError("WEB_SECRET_KEY must be set")`.

Added to `.env.example`:
```
DISCORD_CLIENT_ID=
DISCORD_CLIENT_SECRET=
WEB_BASE_URL=http://localhost:8080
WEB_PORT=8080
WEB_SECRET_KEY=<generate with: python -c "import secrets; print(secrets.token_hex(32))">
WEB_GUILD_ID=
```

---

## Error Handling

| Scenario | Behaviour |
|---|---|
| OAuth callback invalid/expired code | Redirect `/login?error=auth_failed` |
| User not admin in any bot guild | Render login.html with error "Not an administrator in any connected server" |
| Session cookie expired | Redirect `/login?error=session_expired` |
| `/admin purge` confirmation timeout (60s) | Button disables, message updates to "Confirmation timed out." |
| `EditEntryUseCase` — entry not found | Returns `None`; Discord replies ephemeral error; web returns 404 |
| Purge returns 0 deleted | Report "No entries found matching criteria." (not an error) |
| Web form — invalid entry id | 404 redirect to /entries with flash |
| Bot not in `web_guild_id` guild | Dashboard shows zeros; no crash |
| `web_secret_key` not set | `RuntimeError` at startup before bot connects |
| `web_guild_id` not set | Stats return zeros; no crash |
| `FeedRepository.delete` called without channel_id (web admin) | Deletes by id only when `admin=True` |

---

## Testing

| Layer | Approach |
|---|---|
| `BotStats`, `GuildConfig` dataclasses | Plain unit tests, no fixtures |
| `GetStatsUseCase`, `EditEntryUseCase`, `ListByAuthorUseCase`, `PurgeByAuthorUseCase`, `PurgeByTagUseCase`, `GetGuildConfigUseCase`, `SetGuildConfigUseCase` | Real in-memory SQLite, no mocks |
| `SQLAlchemyGuildConfigRepository` | Real SQLite on `tmp_path` |
| `AdminCog` Discord commands | Mock use cases + mock interaction (existing pattern) |
| `ConfirmView` | Test confirm callback invokes use case; test timeout disables button |
| FastAPI routes | `httpx.AsyncClient(app=app, base_url="http://test")` — use cases injected as mocks |
| Discord OAuth (`auth.py`) | Mock `aiohttp` calls; test cookie set/read/expiry |
| `/store` restriction | Test `StoreCog` with mock `GetGuildConfigUseCase` returning `store_restricted=True` and `False` |

pytest-asyncio auto mode throughout — no `@pytest.mark.asyncio` decorators.

Target: ≥85% coverage on all new code.
