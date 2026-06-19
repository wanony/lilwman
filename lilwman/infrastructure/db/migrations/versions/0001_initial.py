"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-06-19

"""
from typing import Sequence, Union
import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "entries",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("author_id", sa.String(), nullable=False),
        sa.Column("author_name", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_table(
        "tags",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("entry_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.ForeignKeyConstraint(["entry_id"], ["entries.id"], ondelete="CASCADE"),
    )
    op.execute(
        """
        CREATE VIRTUAL TABLE entries_fts USING fts5(
            entry_id UNINDEXED,
            content,
            tags
        )
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS entries_fts")
    op.drop_table("tags")
    op.drop_table("entries")
