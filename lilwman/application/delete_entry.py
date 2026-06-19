from lilwman.domain.ports import EntryRepository


class DeleteEntryUseCase:
    def __init__(self, repo: EntryRepository) -> None:
        self._repo = repo

    async def execute(
        self, entry_id: int, author_id: str, is_admin: bool
    ) -> bool:
        return await self._repo.delete(entry_id, author_id, is_admin)
