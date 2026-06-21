from datetime import datetime, timezone, timedelta

from sqlalchemy import select, delete
from sqlalchemy.exc import IntegrityError

from lilwman.domain.feed_entities import FeedSubscription
from lilwman.domain.feed_ports import FeedRepository
from .feed_models import FeedSubscriptionModel, SeenPostModel


class SQLAlchemyFeedRepository(FeedRepository):
    def __init__(self, session_factory) -> None:
        self._session_factory = session_factory

    async def save(
        self, channel_id: str, platform: str, account_name: str,
        rss_url: str, guild_id: str = "",
    ) -> FeedSubscription | None:
        now = datetime.now(timezone.utc)
        model = FeedSubscriptionModel(
            channel_id=channel_id,
            platform=platform,
            account_name=account_name,
            rss_url=rss_url,
            created_at=now,
        )
        async with self._session_factory() as session:
            async with session.begin():
                session.add(model)
                try:
                    await session.flush()
                except IntegrityError:
                    return None
        return FeedSubscription(
            id=model.id,
            channel_id=channel_id,
            platform=platform,
            account_name=account_name,
            rss_url=rss_url,
            created_at=now,
        )

    async def delete(self, feed_id: int, channel_id: str, admin: bool = False) -> bool:
        async with self._session_factory() as session:
            async with session.begin():
                result = await session.execute(
                    select(FeedSubscriptionModel).where(
                        FeedSubscriptionModel.id == feed_id,
                        FeedSubscriptionModel.channel_id == channel_id,
                    )
                )
                model = result.scalar_one_or_none()
                if model is None:
                    return False
                await session.delete(model)
                return True

    async def list_for_channel(self, channel_id: str) -> list[FeedSubscription]:
        async with self._session_factory() as session:
            result = await session.execute(
                select(FeedSubscriptionModel)
                .where(FeedSubscriptionModel.channel_id == channel_id)
                .order_by(FeedSubscriptionModel.created_at.asc())
            )
            return [self._to_entity(m) for m in result.scalars().all()]

    async def list_all(self) -> list[FeedSubscription]:
        async with self._session_factory() as session:
            result = await session.execute(
                select(FeedSubscriptionModel).order_by(FeedSubscriptionModel.id.asc())
            )
            return [self._to_entity(m) for m in result.scalars().all()]

    async def is_seen(self, feed_id: int, guid: str) -> bool:
        async with self._session_factory() as session:
            result = await session.execute(
                select(SeenPostModel).where(
                    SeenPostModel.feed_id == feed_id,
                    SeenPostModel.guid == guid,
                )
            )
            return result.scalar_one_or_none() is not None

    async def mark_seen(self, feed_id: int, guid: str) -> None:
        now = datetime.now(timezone.utc)
        async with self._session_factory() as session:
            async with session.begin():
                session.add(SeenPostModel(feed_id=feed_id, guid=guid, seen_at=now))

    async def prune_seen(self, older_than_days: int) -> None:
        cutoff = datetime.now(timezone.utc) - timedelta(days=older_than_days)
        async with self._session_factory() as session:
            async with session.begin():
                await session.execute(
                    delete(SeenPostModel).where(SeenPostModel.seen_at < cutoff)
                )

    async def count_for_guild(self, guild_id: str) -> int:
        raise NotImplementedError

    def _to_entity(self, model: FeedSubscriptionModel) -> FeedSubscription:
        return FeedSubscription(
            id=model.id,
            channel_id=model.channel_id,
            platform=model.platform,
            account_name=model.account_name,
            rss_url=model.rss_url,
            created_at=model.created_at,
        )
