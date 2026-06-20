# RSS / Social Media Feeds Design

**Date:** 2026-06-21  
**Scope:** Add social media feed subscriptions to the lilwman Discord bot. Users subscribe a channel to an account on any platform via RSS Bridge. The bot polls every 5 minutes and posts new content as Discord embeds — with image galleries and video auto-embed via platform fix URLs.

---

## Architecture

Extends the existing hexagonal (clean) architecture. New code follows the same layering contract as the rest of the project:

```
domain/
  feed_entities.py     — FeedSubscription, FeedPost dataclasses
  feed_ports.py        — FeedRepository ABC, FeedFetcher ABC

application/
  add_feed.py          — AddFeedUseCase: construct RSS Bridge URL, save subscription
  remove_feed.py       — RemoveFeedUseCase: delete subscription by id
  list_feeds.py        — ListFeedsUseCase: return subscriptions for a channel
  poll_feeds.py        — PollFeedsUseCase: fetch all feeds, deduplicate, return new posts

infrastructure/
  db/feed_models.py        — SQLAlchemy ORM models: FeedSubscriptionModel, SeenPostModel
  db/feed_repository.py    — SQLAlchemyFeedRepository implements FeedRepository
  db/migrations/0002_feeds.py
  http/feed_fetcher.py     — AiohttpFeedFetcher implements FeedFetcher (aiohttp + feedparser)

bot/
  commands/feed.py     — FeedCog: /feed add, /feed remove, /feed list, /feed add url
  poller.py            — FeedPoller cog: @tasks.loop(minutes=5), posts embeds to channels

config.py              — adds rss_bridge_url: str field
```

**New dependencies:** `aiohttp` (async HTTP client), `feedparser` (RSS/Atom parsing).

---

## Data Model

### `feed_subscriptions`

| Column | Type | Notes |
|---|---|---|
| id | INTEGER PK | |
| channel_id | TEXT | Discord channel snowflake |
| platform | TEXT | "instagram", "twitter", "tiktok", "youtube", "reddit", "twitch", "hackernews", "custom", etc. |
| account_name | TEXT | username / subreddit / channel ID |
| rss_url | TEXT | Full RSS Bridge URL (constructed on add; stored for polling) |
| created_at | DATETIME | |

Unique constraint: `(channel_id, rss_url)` — prevents duplicate subscriptions in same channel.

### `seen_posts`

| Column | Type | Notes |
|---|---|---|
| id | INTEGER PK | |
| feed_id | INTEGER FK | → feed_subscriptions(id) ON DELETE CASCADE |
| guid | TEXT | RSS entry unique ID |
| seen_at | DATETIME | |

Index on `(feed_id, guid)` for fast dedup lookup. Entries pruned after 30 days.

---

## RSS Bridge URL Construction

`AddFeedUseCase` constructs the RSS Bridge URL from platform + account_name using a mapping:

```python
_BRIDGES = {
    "instagram":  "Instagram&username={account}",
    "tiktok":     "TikTok&username={account}",
    "twitter":    "Twitter&u={account}",
    "reddit":     "Reddit&r={account}",
    "youtube":    "YouTube&channel={account}",
    "twitch":     "Twitch&channel={account}",
    "hackernews": "HackerNews&category={account}",
}

def build_rss_url(rss_bridge_host: str, platform: str, account: str) -> str:
    bridge_params = _BRIDGES[platform].format(account=account)
    return f"{rss_bridge_host}/?action=display&bridge={bridge_params}&format=Atom"
```

**Unknown platform:** user passes a raw RSS URL directly via `/feed add url <url>`. Platform stored as `"custom"`, account_name stored as the URL host for display.

---

## Domain Entities

```python
@dataclass
class FeedSubscription:
    id: int
    channel_id: str
    platform: str
    account_name: str
    rss_url: str
    created_at: datetime

@dataclass
class FeedPost:
    guid: str
    title: str
    url: str
    description: str          # truncated to 300 chars
    author: str
    published_at: datetime
    images: list[str]         # image URLs from media:content / enclosure tags
    video_url: str | None     # video URL if present in feed
```

---

## Commands

`/feed` is an `app_commands.Group`. All subcommands require `interaction.user.guild_permissions.administrator`.

| Command | Args | Behaviour |
|---|---|---|
| `/feed add <platform> <account>` | platform (str), account (str) | Construct RSS Bridge URL, save subscription, confirm with subscription id. |
| `/feed add url <url>` | url (str) | Save raw RSS URL as platform="custom". |
| `/feed remove <id>` | id (int) | Delete subscription by id (must belong to current channel). |
| `/feed list` | — | Embed listing all subscriptions for current channel (id, platform, account). |

---

## Media Posting Strategy

Four cases, evaluated per post in order:

**Case 1 — Video post on supported platform**  
Post the "fix" URL as message content. Discord auto-embeds the video player (same behaviour as vxtwitter / ddinstagram).

```python
_FIX_URLS = {
    "twitter":   lambda u: u.replace("x.com", "vxtwitter.com").replace("twitter.com", "vxtwitter.com"),
    "instagram": lambda u: u.replace("instagram.com", "ddinstagram.com"),
    "tiktok":    lambda u: u.replace("tiktok.com", "vxtiktok.com"),
}
```

**Case 2 — Single image post**  
Rich embed with `embed.set_image(url=images[0])`. Includes title, author, description snippet, timestamp, platform colour.

**Case 3 — Multiple images (carousel)**  
Rich embed with first image + `◀ ▶` paginator buttons (`FeedImagePaginator`). Footer shows "Image 1/3". User scrolls through remaining images. Timeout: 120 seconds.

**Case 4 — Text / link only (fallback)**  
Rich embed: title, description snippet (300 chars), author, URL, timestamp, platform colour.

Platform colours:
```python
_COLOURS = {
    "instagram": 0xE1306C,
    "tiktok":    0x010101,
    "twitter":   0x1DA1F2,
    "reddit":    0xFF4500,
    "youtube":   0xFF0000,
    "twitch":    0x9146FF,
    "hackernews":0xFF6600,
    "custom":    0x5865F2,
}
```

---

## Polling Flow

`FeedPoller` is a `commands.Cog` with a `@tasks.loop(minutes=5)` coroutine. Errors are caught per-feed so one bad feed never blocks the others.

```
for each FeedSubscription:
  try:
    posts = await fetcher.fetch(subscription.rss_url)  → list[FeedPost]
    new_posts = [p for p in posts if not await repo.is_seen(subscription.id, p.guid)]
    new_posts = sorted(new_posts, key=lambda p: p.published_at)[:5]  # cap 5, oldest first
    for post in new_posts:
      await post_to_channel(channel_id, post, platform)
      await repo.mark_seen(subscription.id, post.guid)
  except Exception:
    log.warning("Feed poll failed for %s", subscription.rss_url)
    continue

await repo.prune_seen(older_than_days=30)
```

Cap of 5 new posts per feed per poll — prevents spam on first subscription or after a long gap.

---

## Error Handling

| Scenario | Behaviour |
|---|---|
| RSS Bridge unreachable / timeout | Log warning, skip feed, retry next cycle |
| Feed returns 404 / invalid XML | Log warning, skip feed, do not remove subscription |
| Discord channel deleted / bot lacks send permission | Log error, skip post, do not remove subscription |
| Platform not in `_FIX_URLS` mapping | Fall back to Case 4 (plain embed with original URL) |
| Image URL invalid in embed | Discord silently ignores bad `set_image` URL — acceptable |
| Duplicate GUID (two poll cycles overlap) | Unique constraint on `(feed_id, guid)` absorbs conflict silently |

---

## Testing Strategy

| Layer | Approach |
|---|---|
| Domain entities | Plain unit tests, no fixtures |
| `AddFeedUseCase` / `RemoveFeedUseCase` / `ListFeedsUseCase` / `PollFeedsUseCase` | Real in-memory SQLite, mock `FeedFetcher` |
| `SQLAlchemyFeedRepository` | Real SQLite on `tmp_path` |
| `AiohttpFeedFetcher` | Mock `aiohttp.ClientSession`; parse fixture Atom XML strings |
| `FeedCog` commands | Mock use cases, mock interaction (same pattern as existing cog tests) |
| `FeedPoller` | Mock `PollFeedsUseCase`; verify loop fires and posts to channel |
| Fix URL transforms | Pure unit tests (string → string) |
| `FeedImagePaginator` | Same pattern as `SearchPaginator` tests |

Target: ≥85% coverage on all new code.

---

## Configuration

One new field added to `Settings` in `config.py`:

```python
rss_bridge_url: str = "http://localhost:3000"
```

Added to `.env.example` and `__main__.py` wiring.

---

## Wiring (`__main__.py`)

```python
feed_repo = SQLAlchemyFeedRepository(session_factory)
feed_fetcher = AiohttpFeedFetcher()
add_feed = AddFeedUseCase(feed_repo, settings.rss_bridge_url)
remove_feed = RemoveFeedUseCase(feed_repo)
list_feeds = ListFeedsUseCase(feed_repo)
poll_feeds = PollFeedsUseCase(feed_repo, feed_fetcher)

# passed to bot
bot = LilwmanBot(..., add_feed=add_feed, remove_feed=remove_feed,
                 list_feeds=list_feeds, poll_feeds=poll_feeds)
```

`FeedCog` and `FeedPoller` added in `setup_hook`.
