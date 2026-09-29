"""ORM entities. Schema changes must go through an Alembic migration."""

from datetime import UTC, datetime
from typing import Any, ClassVar

from sqlalchemy import (
    JSON,
    BigInteger,
    DateTime,
    ForeignKey,
    MetaData,
    String,
    Text,
    UniqueConstraint,
    false,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utcnow() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    type_annotation_map: ClassVar[dict[Any, Any]] = {datetime: DateTime(timezone=True)}
    # Deterministic constraint names keep migrations portable between SQLite and PostgreSQL.
    metadata = MetaData(
        naming_convention={
            "ix": "ix_%(column_0_label)s",
            "uq": "uq_%(table_name)s_%(column_0_name)s",
            "ck": "ck_%(table_name)s_%(constraint_name)s",
            "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
            "pk": "pk_%(table_name)s",
        }
    )


class DiffusionModel(Base):
    __tablename__ = "models"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    # Path relative to MODEL_DIRECTORY, so the storage folder can be moved.
    path: Mapped[str] = mapped_column(String(1024), unique=True)
    source_type: Mapped[str] = mapped_column(String(32))
    architecture: Mapped[str] = mapped_column(String(32))
    file_size_bytes: Mapped[int] = mapped_column(BigInteger)
    description: Mapped[str] = mapped_column(Text, default="")
    preview_image_path: Mapped[str | None] = mapped_column(String(1024))
    supported_resolutions: Mapped[list[list[int]]] = mapped_column(JSON, default=list)
    # False when the files disappeared from disk; kept so history links stay meaningful.
    available: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)


class Lora(Base):
    __tablename__ = "loras"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    # Filename inside LORA_DIRECTORY (never a user-supplied path).
    filename: Mapped[str] = mapped_column(String(255), unique=True)
    file_size_bytes: Mapped[int] = mapped_column(BigInteger)
    base_architecture: Mapped[str] = mapped_column(String(32))
    rank: Mapped[int | None]
    enabled: Mapped[bool] = mapped_column(default=True)
    default_strength: Mapped[float] = mapped_column(default=1.0)
    trigger_words: Mapped[str] = mapped_column(Text, default="")
    description: Mapped[str] = mapped_column(Text, default="")
    preview_image_path: Mapped[str | None] = mapped_column(String(1024))
    available: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)


class Generation(Base):
    __tablename__ = "generations"

    id: Mapped[int] = mapped_column(primary_key=True)
    created_at: Mapped[datetime] = mapped_column(default=utcnow, index=True)
    prompt: Mapped[str] = mapped_column(Text)
    negative_prompt: Mapped[str] = mapped_column(Text, default="")
    # Foreign keys go NULL on delete; the *_name snapshots keep history readable afterwards.
    model_id: Mapped[int | None] = mapped_column(
        ForeignKey("models.id", ondelete="SET NULL"), index=True
    )
    model_name: Mapped[str] = mapped_column(String(255))
    lora_id: Mapped[int | None] = mapped_column(
        ForeignKey("loras.id", ondelete="SET NULL"), index=True
    )
    lora_name: Mapped[str | None] = mapped_column(String(255))
    lora_strength: Mapped[float | None]
    seed: Mapped[int] = mapped_column(BigInteger)
    width: Mapped[int]
    height: Mapped[int]
    steps: Mapped[int]
    guidance_scale: Mapped[float]
    num_images: Mapped[int]
    duration_ms: Mapped[int]
    device: Mapped[str] = mapped_column(String(32))
    model_config_json: Mapped[dict[str, Any]] = mapped_column("model_config", JSON, default=dict)
    # Set when this generation is one cell of a comparison; the index is its position.
    comparison_id: Mapped[int | None] = mapped_column(
        ForeignKey("comparisons.id", ondelete="SET NULL"), index=True
    )
    comparison_index: Mapped[int | None]

    images: Mapped[list["GenerationImage"]] = relationship(
        back_populates="generation",
        cascade="all, delete-orphan",
        order_by="GenerationImage.index",
    )
    comparison: Mapped["Comparison | None"] = relationship(back_populates="generations")


class Comparison(Base):
    """One prompt generated several times, varying a single setting (the axis)."""

    __tablename__ = "comparisons"

    id: Mapped[int] = mapped_column(primary_key=True)
    created_at: Mapped[datetime] = mapped_column(default=utcnow, index=True)
    prompt: Mapped[str] = mapped_column(Text)
    # "lora_strength" | "seed" | "model"
    axis: Mapped[str] = mapped_column(String(32))
    # One entry per cell, in display order. Cells missing from `generations` were not produced.
    axis_values: Mapped[list[Any]] = mapped_column(JSON)
    # "running" | "completed" | "cancelled" | "failed" | "interrupted"
    status: Mapped[str] = mapped_column(String(16), default="running")
    error_message: Mapped[str | None] = mapped_column(Text)

    generations: Mapped[list[Generation]] = relationship(
        back_populates="comparison", order_by="Generation.comparison_index"
    )


class GenerationImage(Base):
    __tablename__ = "generation_images"

    id: Mapped[int] = mapped_column(primary_key=True)
    generation_id: Mapped[int] = mapped_column(
        ForeignKey("generations.id", ondelete="CASCADE"), index=True
    )
    index: Mapped[int]
    seed: Mapped[int] = mapped_column(BigInteger)
    # Path relative to OUTPUT_DIRECTORY.
    file_path: Mapped[str] = mapped_column(String(1024))
    width: Mapped[int]
    height: Mapped[int]
    file_size_bytes: Mapped[int] = mapped_column(BigInteger)
    # The model's safety checker replaced this image with a black one.
    safety_blocked: Mapped[bool] = mapped_column(default=False, server_default=false())
    created_at: Mapped[datetime] = mapped_column(default=utcnow)

    generation: Mapped[Generation] = relationship(back_populates="images")


class Dataset(Base):
    """A collection of images (and captions) prepared for LoRA training."""

    __tablename__ = "datasets"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text, default="")
    # Shortest side images should have; smaller ones are flagged as low resolution.
    target_resolution: Mapped[int] = mapped_column(default=512)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=utcnow, onupdate=utcnow)

    images: Mapped[list["DatasetImage"]] = relationship(
        back_populates="dataset",
        cascade="all, delete-orphan",
        order_by="DatasetImage.position",
    )


class DatasetImage(Base):
    __tablename__ = "dataset_images"
    # The same bytes can't be added to a dataset twice.
    __table_args__ = (UniqueConstraint("dataset_id", "sha256"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    dataset_id: Mapped[int] = mapped_column(
        ForeignKey("datasets.id", ondelete="CASCADE"), index=True
    )
    position: Mapped[int]
    # Shown to users only; files on disk use generated names.
    original_filename: Mapped[str] = mapped_column(String(255))
    stored_filename: Mapped[str] = mapped_column(String(64))
    format: Mapped[str] = mapped_column(String(8))
    width: Mapped[int]
    height: Mapped[int]
    file_size_bytes: Mapped[int] = mapped_column(BigInteger)
    sha256: Mapped[str] = mapped_column(String(64))
    perceptual_hash: Mapped[str] = mapped_column(String(16))
    blur_score: Mapped[float]
    caption: Mapped[str] = mapped_column(Text, default="")
    # Who wrote the caption ("manual" now; AI captioning will add another source) and when.
    # AI captioning must not overwrite manual captions without confirmation.
    caption_source: Mapped[str | None] = mapped_column(String(16))
    caption_updated_at: Mapped[datetime | None]
    created_at: Mapped[datetime] = mapped_column(default=utcnow)

    dataset: Mapped[Dataset] = relationship(back_populates="images")


class ApplicationSetting(Base):
    __tablename__ = "application_settings"

    key: Mapped[str] = mapped_column(String(128), primary_key=True)
    value: Mapped[dict[str, Any]] = mapped_column(JSON)
    updated_at: Mapped[datetime] = mapped_column(default=utcnow, onupdate=utcnow)
