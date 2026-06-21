from datetime import datetime

from sqlalchemy import Integer, String, DateTime, ForeignKey, UniqueConstraint, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .models import Base


class FeedSubscriptionModel(Base):
    __tablename__ = "feed_subscriptions"
    __table_args__ = (
        UniqueConstraint("channel_id", "rss_url", name="uq_channel_rss_url"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    channel_id: Mapped[str] = mapped_column(String, nullable=False)
    guild_id: Mapped[str] = mapped_column(String, nullable=False, default="")
    platform: Mapped[str] = mapped_column(String, nullable=False)
    account_name: Mapped[str] = mapped_column(String, nullable=False)
    rss_url: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    seen_posts: Mapped[list["SeenPostModel"]] = relationship(
        back_populates="subscription", cascade="all, delete-orphan"
    )


class SeenPostModel(Base):
    __tablename__ = "seen_posts"
    __table_args__ = (
        Index("ix_seen_posts_feed_guid", "feed_id", "guid"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    feed_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("feed_subscriptions.id", ondelete="CASCADE"), nullable=False
    )
    guid: Mapped[str] = mapped_column(String, nullable=False)
    seen_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    subscription: Mapped["FeedSubscriptionModel"] = relationship(back_populates="seen_posts")
