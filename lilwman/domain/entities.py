from dataclasses import dataclass
from datetime import datetime


@dataclass
class Entry:
    id: int
    content: str
    tags: list[str]
    author_id: str
    author_name: str
    created_at: datetime
    updated_at: datetime
    guild_id: str = ""
