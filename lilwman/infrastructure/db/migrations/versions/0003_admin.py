"""add guild_configs table, guild_id to entries and feed_subscriptions

Revision ID: 0003
Revises: 0002
Create Date: 2026-06-21
"""
from typing import Sequence, Union
import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "guild_configs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("guild_id", sa.String(), nullable=False, unique=True),
        sa.Column("store_restricted", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.add_column("entries", sa.Column("guild_id", sa.String(), nullable=False, server_default=""))
    op.add_column("feed_subscriptions", sa.Column("guild_id", sa.String(), nullable=False, server_default=""))


def downgrade() -> None:
    op.drop_column("feed_subscriptions", "guild_id")
    op.drop_column("entries", "guild_id")
    op.drop_table("guild_configs")
