from lilwman.domain.admin_entities import GuildConfig
from lilwman.domain.admin_ports import GuildConfigRepository


class GetGuildConfigUseCase:
    def __init__(self, config_repo: GuildConfigRepository) -> None:
        self._repo = config_repo

    async def execute(self, guild_id: str) -> GuildConfig:
        return await self._repo.get(guild_id)
