from abc import ABC, abstractmethod
from .admin_entities import GuildConfig


class GuildConfigRepository(ABC):
    @abstractmethod
    async def get(self, guild_id: str) -> GuildConfig: ...

    @abstractmethod
    async def save(self, guild_id: str, store_restricted: bool) -> GuildConfig: ...
