from lilwman.domain.ports import EntryRepository


class PurgeByTagUseCase:
    def __init__(self, repo: EntryRepository) -> None:
        self._repo = repo

    async def execute(self, tag: str, guild_id: str = "") -> int:
        return await self._repo.purge_by_tag(tag, guild_id=guild_id)
