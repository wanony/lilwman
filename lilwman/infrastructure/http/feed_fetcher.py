import re
import calendar
import aiohttp
import feedparser

from datetime import datetime, timezone

from lilwman.domain.feed_entities import FeedPost
from lilwman.domain.feed_ports import FeedFetcher

_TIMEOUT = aiohttp.ClientTimeout(total=15)


class AiohttpFeedFetcher(FeedFetcher):
    async def fetch(self, url: str) -> list[FeedPost]:
        async with aiohttp.ClientSession(timeout=_TIMEOUT) as session:
            async with session.get(url) as response:
                response.raise_for_status()
                content = await response.text()
        return _parse_feed(content)


def _parse_feed(content: str) -> list[FeedPost]:
    parsed = feedparser.parse(content)
    posts = []
    for entry in parsed.entries:
        guid = entry.get("id") or entry.get("link", "")
        title = entry.get("title", "")[:256]
        url = entry.get("link", "")
        description = _strip_html(entry.get("summary", ""))[:300]
        author = entry.get("author", "")
        published_at = _parse_date(entry)
        images = _extract_images(entry)
        video_url = _extract_video(entry)
        posts.append(FeedPost(
            guid=guid,
            title=title,
            url=url,
            description=description,
            author=author,
            published_at=published_at,
            images=images,
            video_url=video_url,
        ))
    return posts


def _parse_date(entry) -> datetime:
    if getattr(entry, "published_parsed", None):
        return datetime.fromtimestamp(
            calendar.timegm(entry.published_parsed), tz=timezone.utc
        )
    return datetime.now(timezone.utc)


def _strip_html(text: str) -> str:
    return re.sub(r"<[^>]+>", "", text).strip()


def _extract_images(entry) -> list[str]:
    images = []
    for media in getattr(entry, "media_content", []):
        if media.get("medium") == "image" and media.get("url"):
            images.append(media["url"])
    if not images:
        for enc in getattr(entry, "enclosures", []):
            if enc.get("type", "").startswith("image/") and enc.get("href"):
                images.append(enc["href"])
    return images


def _extract_video(entry) -> str | None:
    for media in getattr(entry, "media_content", []):
        if media.get("medium") == "video" and media.get("url"):
            return media["url"]
    for enc in getattr(entry, "enclosures", []):
        if enc.get("type", "").startswith("video/") and enc.get("href"):
            return enc["href"]
    return None
