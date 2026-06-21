from lilwman.domain.entities import Entry
from lilwman.domain.ports import EntryRepository


class ListAllEntriesUseCase:
    def __init__(self, repo: EntryRepository) -> None:
        self._repo = repo

    async def execute(
        self, guild_id: str = "", page: int = 1, per_page: int = 20
    ) -> tuple[list[Entry], int]:
        offset = (page - 1) * per_page
        return await self._repo.list_all(guild_id=guild_id, offset=offset, limit=per_page)
