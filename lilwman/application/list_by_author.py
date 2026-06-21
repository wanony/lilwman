from lilwman.domain.entities import Entry
from lilwman.domain.ports import EntryRepository


class ListByAuthorUseCase:
    def __init__(self, repo: EntryRepository) -> None:
        self._repo = repo

    async def execute(self, author_id: str, guild_id: str = "") -> list[Entry]:
        return await self._repo.list_by_author(author_id, guild_id=guild_id)
