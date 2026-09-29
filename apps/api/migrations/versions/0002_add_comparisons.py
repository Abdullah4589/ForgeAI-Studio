"""add comparisons

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-29 17:35:21.909116
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "comparisons",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("prompt", sa.Text(), nullable=False),
        sa.Column("axis", sa.String(length=32), nullable=False),
        sa.Column("axis_values", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_comparisons")),
    )
    with op.batch_alter_table("comparisons", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_comparisons_created_at"), ["created_at"], unique=False)

    with op.batch_alter_table("generations", schema=None) as batch_op:
        batch_op.add_column(sa.Column("comparison_id", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("comparison_index", sa.Integer(), nullable=True))
        batch_op.create_index(
            batch_op.f("ix_generations_comparison_id"), ["comparison_id"], unique=False
        )
        batch_op.create_foreign_key(
            batch_op.f("fk_generations_comparison_id_comparisons"),
            "comparisons",
            ["comparison_id"],
            ["id"],
            ondelete="SET NULL",
        )


def downgrade() -> None:
    with op.batch_alter_table("generations", schema=None) as batch_op:
        batch_op.drop_constraint(
            batch_op.f("fk_generations_comparison_id_comparisons"), type_="foreignkey"
        )
        batch_op.drop_index(batch_op.f("ix_generations_comparison_id"))
        batch_op.drop_column("comparison_index")
        batch_op.drop_column("comparison_id")

    with op.batch_alter_table("comparisons", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_comparisons_created_at"))

    op.drop_table("comparisons")
