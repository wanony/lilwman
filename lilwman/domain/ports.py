from abc import ABC, abstractmethod
from .entities import Entry


class EntryRepository(ABC):
    @abstractmethod
    async def save(
        self,
        content: str,
        tags: list[str],
        author_id: str,
        author_name: str,
        guild_id: str = "",
    ) -> Entry: ...

    @abstractmethod
    async def get_by_id(self, entry_id: int) -> Entry | None: ...

    @abstractmethod
    async def search(self, query: str, limit: int = 20) -> list[Entry]: ...

    @abstractmethod
    async def list_by_tag(self, tag: str) -> list[Entry]: ...

    @abstractmethod
    async def delete(self, entry_id: int, author_id: str, is_admin: bool) -> bool: ...

    @abstractmethod
    async def list_by_author(self, author_id: str, guild_id: str = "") -> list[Entry]: ...

    @abstractmethod
    async def list_all(
        self, guild_id: str = "", offset: int = 0, limit: int = 20
    ) -> tuple[list[Entry], int]: ...

    @abstractmethod
    async def update(self, entry_id: int, content: str, tags: list[str]) -> Entry | None: ...

    @abstractmethod
    async def get_stats(self, guild_id: str) -> dict: ...

    @abstractmethod
    async def purge_by_author(self, author_id: str, guild_id: str = "") -> int: ...

    @abstractmethod
    async def purge_by_tag(self, tag: str, guild_id: str = "") -> int: ...


class LLMPort(ABC):
    @abstractmethod
    async def generate(self, prompt: str) -> str: ...
