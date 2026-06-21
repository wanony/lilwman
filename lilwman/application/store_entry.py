from lilwman.domain.entities import Entry
from lilwman.domain.ports import EntryRepository


class StoreEntryUseCase:
    def __init__(self, repo: EntryRepository) -> None:
        self._repo = repo

    async def execute(
        self,
        content: str,
        tags: list[str],
        author_id: str,
        author_name: str,
        guild_id: str = "",
    ) -> Entry:
        return await self._repo.save(content, tags, author_id, author_name, guild_id=guild_id)
