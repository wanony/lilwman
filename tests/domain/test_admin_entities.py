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
    now = datetime.now(timezone.utc)
    e = Entry(
        id=1, content="x", tags=[], author_id="1",
        author_name="a", created_at=now, updated_at=now,
    )
    assert e.guild_id == ""


def test_feed_subscription_guild_id_defaults_empty():
    from lilwman.domain.feed_entities import FeedSubscription
    now = datetime.now(timezone.utc)
    sub = FeedSubscription(
        id=1, channel_id="c", platform="reddit",
        account_name="python", rss_url="http://x.com",
        created_at=now,
    )
    assert sub.guild_id == ""
