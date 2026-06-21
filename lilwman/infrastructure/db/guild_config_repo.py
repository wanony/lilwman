from datetime import datetime, timezone

from sqlalchemy import select

from lilwman.domain.admin_entities import GuildConfig
from lilwman.domain.admin_ports import GuildConfigRepository
from .guild_config_models import GuildConfigModel


class SQLAlchemyGuildConfigRepository(GuildConfigRepository):
    def __init__(self, session_factory) -> None:
        self._session_factory = session_factory

    async def get(self, guild_id: str) -> GuildConfig:
        async with self._session_factory() as session:
            result = await session.execute(
                select(GuildConfigModel).where(GuildConfigModel.guild_id == guild_id)
            )
            model = result.scalar_one_or_none()
            if model is None:
                now = datetime.now(timezone.utc)
                return GuildConfig(
                    guild_id=guild_id,
                    store_restricted=False,
                    created_at=now,
                    updated_at=now,
                )
            return self._to_entity(model)

    async def save(self, guild_id: str, store_restricted: bool) -> GuildConfig:
        now = datetime.now(timezone.utc)
        async with self._session_factory() as session:
            async with session.begin():
                result = await session.execute(
                    select(GuildConfigModel).where(GuildConfigModel.guild_id == guild_id)
                )
                model = result.scalar_one_or_none()
                if model is None:
                    model = GuildConfigModel(
                        guild_id=guild_id,
                        store_restricted=store_restricted,
                        created_at=now,
                        updated_at=now,
                    )
                    session.add(model)
                else:
                    model.store_restricted = store_restricted
                    model.updated_at = now
                created_at = model.created_at
        return GuildConfig(
            guild_id=guild_id,
            store_restricted=store_restricted,
            created_at=created_at,
            updated_at=now,
        )

    def _to_entity(self, model: GuildConfigModel) -> GuildConfig:
        return GuildConfig(
            guild_id=model.guild_id,
            store_restricted=model.store_restricted,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )
