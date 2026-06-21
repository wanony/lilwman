from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class BotStats:
    total_entries: int
    entries_this_week: int
    entries_this_month: int
    total_feeds: int
    unique_tags: int
    top_tags: list[tuple[str, int]] = field(default_factory=list)
    top_authors: list[tuple[str, int]] = field(default_factory=list)


@dataclass
class GuildConfig:
    guild_id: str
    store_restricted: bool
    created_at: datetime
    updated_at: datetime
