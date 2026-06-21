from lilwman.domain.entities import Entry
from lilwman.domain.ports import EntryRepository


class GetEntryUseCase:
    def __init__(self, repo: EntryRepository) -> None:
        self._repo = repo

    async def execute(self, entry_id: int) -> Entry | None:
        return await self._repo.get_by_id(entry_id)
