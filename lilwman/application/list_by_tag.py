from lilwman.domain.entities import Entry
from lilwman.domain.ports import EntryRepository


class ListByTagUseCase:
    def __init__(self, repo: EntryRepository) -> None:
        self._repo = repo

    async def execute(self, tag: str) -> list[Entry]:
        return await self._repo.list_by_tag(tag)
