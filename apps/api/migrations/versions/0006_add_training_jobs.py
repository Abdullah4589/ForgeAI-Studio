"""add training jobs

Revision ID: 0006
Revises: 0005
Create Date: 2026-09-30 17:01:43.073230
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "training_jobs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("dataset_id", sa.Integer(), nullable=True),
        sa.Column("dataset_name", sa.String(length=255), nullable=False),
        sa.Column("base_model_id", sa.Integer(), nullable=True),
        sa.Column("base_model_name", sa.String(length=255), nullable=False),
        sa.Column("trigger_word", sa.String(length=100), nullable=False),
        sa.Column("resolution", sa.Integer(), nullable=False),
        sa.Column("rank", sa.Integer(), nullable=False),
        sa.Column("alpha", sa.Double(), nullable=False),
        sa.Column("learning_rate", sa.Double(), nullable=False),
        sa.Column("batch_size", sa.Integer(), nullable=False),
        sa.Column("steps", sa.Integer(), nullable=False),
        sa.Column("save_every", sa.Integer(), nullable=False),
        sa.Column("seed", sa.BigInteger(), nullable=False),
        sa.Column("sample_count", sa.Integer(), nullable=False),
        sa.Column("sample_steps", sa.Integer(), nullable=False),
        sa.Column("image_count", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("job_id", sa.String(length=64), nullable=True),
        sa.Column("current_step", sa.Integer(), nullable=False),
        sa.Column("last_loss", sa.Double(), nullable=True),
        sa.Column("loss_history", sa.JSON(), nullable=False),
        sa.Column("peak_memory_bytes", sa.BigInteger(), nullable=True),
        sa.Column("avg_step_seconds", sa.Double(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("lora_id", sa.Integer(), nullable=True),
        sa.Column("last_checkpoint", sa.String(length=1024), nullable=True),
        sa.Column("samples", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(
            ["base_model_id"],
            ["models.id"],
            name=op.f("fk_training_jobs_base_model_id_models"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["dataset_id"],
            ["datasets.id"],
            name=op.f("fk_training_jobs_dataset_id_datasets"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["lora_id"],
            ["loras.id"],
            name=op.f("fk_training_jobs_lora_id_loras"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_training_jobs")),
    )
    with op.batch_alter_table("training_jobs", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_training_jobs_created_at"), ["created_at"], unique=False
        )
        batch_op.create_index(
            batch_op.f("ix_training_jobs_dataset_id"), ["dataset_id"], unique=False
        )


def downgrade() -> None:
    with op.batch_alter_table("training_jobs", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_training_jobs_dataset_id"))
        batch_op.drop_index(batch_op.f("ix_training_jobs_created_at"))

    op.drop_table("training_jobs")
