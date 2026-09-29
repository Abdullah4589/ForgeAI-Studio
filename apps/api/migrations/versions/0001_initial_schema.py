"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-09-29 14:47:11.038607
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:

    op.create_table(
        "application_settings",
        sa.Column("key", sa.String(length=128), nullable=False),
        sa.Column("value", sa.JSON(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("key", name=op.f("pk_application_settings")),
    )
    op.create_table(
        "loras",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("file_size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("base_architecture", sa.String(length=32), nullable=False),
        sa.Column("rank", sa.Integer(), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("default_strength", sa.Double(), nullable=False),
        sa.Column("trigger_words", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("preview_image_path", sa.String(length=1024), nullable=True),
        sa.Column("available", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_loras")),
        sa.UniqueConstraint("filename", name=op.f("uq_loras_filename")),
    )
    op.create_table(
        "models",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("path", sa.String(length=1024), nullable=False),
        sa.Column("source_type", sa.String(length=32), nullable=False),
        sa.Column("architecture", sa.String(length=32), nullable=False),
        sa.Column("file_size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("preview_image_path", sa.String(length=1024), nullable=True),
        sa.Column("supported_resolutions", sa.JSON(), nullable=False),
        sa.Column("available", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_models")),
        sa.UniqueConstraint("path", name=op.f("uq_models_path")),
    )
    op.create_table(
        "generations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("prompt", sa.Text(), nullable=False),
        sa.Column("negative_prompt", sa.Text(), nullable=False),
        sa.Column("model_id", sa.Integer(), nullable=True),
        sa.Column("model_name", sa.String(length=255), nullable=False),
        sa.Column("lora_id", sa.Integer(), nullable=True),
        sa.Column("lora_name", sa.String(length=255), nullable=True),
        sa.Column("lora_strength", sa.Double(), nullable=True),
        sa.Column("seed", sa.BigInteger(), nullable=False),
        sa.Column("width", sa.Integer(), nullable=False),
        sa.Column("height", sa.Integer(), nullable=False),
        sa.Column("steps", sa.Integer(), nullable=False),
        sa.Column("guidance_scale", sa.Double(), nullable=False),
        sa.Column("num_images", sa.Integer(), nullable=False),
        sa.Column("duration_ms", sa.Integer(), nullable=False),
        sa.Column("device", sa.String(length=32), nullable=False),
        sa.Column("model_config", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(
            ["lora_id"],
            ["loras.id"],
            name=op.f("fk_generations_lora_id_loras"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["model_id"],
            ["models.id"],
            name=op.f("fk_generations_model_id_models"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_generations")),
    )
    with op.batch_alter_table("generations", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_generations_created_at"), ["created_at"], unique=False)
        batch_op.create_index(batch_op.f("ix_generations_lora_id"), ["lora_id"], unique=False)
        batch_op.create_index(batch_op.f("ix_generations_model_id"), ["model_id"], unique=False)

    op.create_table(
        "generation_images",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("generation_id", sa.Integer(), nullable=False),
        sa.Column("index", sa.Integer(), nullable=False),
        sa.Column("seed", sa.BigInteger(), nullable=False),
        sa.Column("file_path", sa.String(length=1024), nullable=False),
        sa.Column("width", sa.Integer(), nullable=False),
        sa.Column("height", sa.Integer(), nullable=False),
        sa.Column("file_size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["generation_id"],
            ["generations.id"],
            name=op.f("fk_generation_images_generation_id_generations"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_generation_images")),
    )
    with op.batch_alter_table("generation_images", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_generation_images_generation_id"), ["generation_id"], unique=False
        )


def downgrade() -> None:

    with op.batch_alter_table("generation_images", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_generation_images_generation_id"))

    op.drop_table("generation_images")
    with op.batch_alter_table("generations", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_generations_model_id"))
        batch_op.drop_index(batch_op.f("ix_generations_lora_id"))
        batch_op.drop_index(batch_op.f("ix_generations_created_at"))

    op.drop_table("generations")
    op.drop_table("models")
    op.drop_table("loras")
    op.drop_table("application_settings")
