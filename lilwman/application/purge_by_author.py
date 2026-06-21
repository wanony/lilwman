from lilwman.domain.ports import EntryRepository


class PurgeByAuthorUseCase:
    def __init__(self, repo: EntryRepository) -> None:
        self._repo = repo

    async def execute(self, author_id: str, guild_id: str = "") -> int:
        return await self._repo.purge_by_author(author_id, guild_id=guild_id)
