from lilwman.domain.entities import Entry
from lilwman.domain.ports import EntryRepository


class SearchEntriesUseCase:
    def __init__(self, repo: EntryRepository) -> None:
        self._repo = repo

    async def execute(self, query: str) -> list[Entry]:
        return await self._repo.search(query, limit=20)
