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
    ) -> Entry: ...

    @abstractmethod
    async def get_by_id(self, entry_id: int) -> Entry | None: ...

    @abstractmethod
    async def search(self, query: str, limit: int = 20) -> list[Entry]: ...

    @abstractmethod
    async def list_by_tag(self, tag: str) -> list[Entry]: ...

    @abstractmethod
    async def delete(
        self, entry_id: int, author_id: str, is_admin: bool
    ) -> bool: ...


class LLMPort(ABC):
    @abstractmethod
    async def generate(self, prompt: str) -> str: ...
