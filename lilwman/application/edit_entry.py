from lilwman.domain.entities import Entry
from lilwman.domain.ports import EntryRepository


class EditEntryUseCase:
    def __init__(self, repo: EntryRepository) -> None:
        self._repo = repo

    async def execute(self, entry_id: int, content: str, tags: list[str]) -> Entry | None:
        return await self._repo.update(entry_id, content, tags)
