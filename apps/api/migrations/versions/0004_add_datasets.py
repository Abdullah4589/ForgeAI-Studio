"""add datasets

Revision ID: 0004
Revises: 0003
Create Date: 2026-09-29 18:58:44.421607
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "datasets",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("target_resolution", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_datasets")),
    )
    op.create_table(
        "dataset_images",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("dataset_id", sa.Integer(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("original_filename", sa.String(length=255), nullable=False),
        sa.Column("stored_filename", sa.String(length=64), nullable=False),
        sa.Column("format", sa.String(length=8), nullable=False),
        sa.Column("width", sa.Integer(), nullable=False),
        sa.Column("height", sa.Integer(), nullable=False),
        sa.Column("file_size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("perceptual_hash", sa.String(length=16), nullable=False),
        sa.Column("blur_score", sa.Double(), nullable=False),
        sa.Column("caption", sa.Text(), nullable=False),
        sa.Column("caption_source", sa.String(length=16), nullable=True),
        sa.Column("caption_updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["dataset_id"],
            ["datasets.id"],
            name=op.f("fk_dataset_images_dataset_id_datasets"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_dataset_images")),
        sa.UniqueConstraint("dataset_id", "sha256", name=op.f("uq_dataset_images_dataset_id")),
    )
    with op.batch_alter_table("dataset_images", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_dataset_images_dataset_id"), ["dataset_id"], unique=False
        )


def downgrade() -> None:
    with op.batch_alter_table("dataset_images", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_dataset_images_dataset_id"))

    op.drop_table("dataset_images")
    op.drop_table("datasets")
