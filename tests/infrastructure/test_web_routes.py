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
