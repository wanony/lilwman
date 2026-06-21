"""add feed_subscriptions and seen_posts tables

Revision ID: 0002
Revises: 0001
Create Date: 2026-06-21
"""
from typing import Sequence, Union
import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "feed_subscriptions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("channel_id", sa.String(), nullable=False),
        sa.Column("platform", sa.String(), nullable=False),
        sa.Column("account_name", sa.String(), nullable=False),
        sa.Column("rss_url", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("channel_id", "rss_url", name="uq_channel_rss_url"),
    )
    op.create_table(
        "seen_posts",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("feed_id", sa.Integer(), nullable=False),
        sa.Column("guid", sa.String(), nullable=False),
        sa.Column("seen_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["feed_id"], ["feed_subscriptions.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_seen_posts_feed_guid", "seen_posts", ["feed_id", "guid"])


def downgrade() -> None:
    op.drop_index("ix_seen_posts_feed_guid", table_name="seen_posts")
    op.drop_table("seen_posts")
    op.drop_table("feed_subscriptions")
