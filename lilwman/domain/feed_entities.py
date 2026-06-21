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
