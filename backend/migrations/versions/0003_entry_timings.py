"""Entry timings: how long each entry took, as numbers only (the dashboard's entry speed).

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-28
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "entry_timings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("shop_id", sa.Integer(), nullable=False),
        sa.Column("duration_ms", sa.Integer(), nullable=False),
        sa.Column(
            "input_method",
            sa.Enum(
                "typed",
                "voice",
                name="input_method",
                native_enum=False,
                create_constraint=True,
                length=10,
            ),
            nullable=False,
        ),
        sa.Column("entry_count", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["shop_id"], ["shops.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_entry_timings_shop_created", "entry_timings", ["shop_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_entry_timings_shop_created", table_name="entry_timings")
    op.drop_table("entry_timings")
