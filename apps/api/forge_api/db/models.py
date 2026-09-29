"""ORM entities. Schema changes must go through an Alembic migration."""

from datetime import UTC, datetime
from typing import Any, ClassVar

from sqlalchemy import JSON, BigInteger, DateTime, ForeignKey, MetaData, String, Text
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

    images: Mapped[list["GenerationImage"]] = relationship(
        back_populates="generation",
        cascade="all, delete-orphan",
        order_by="GenerationImage.index",
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
    created_at: Mapped[datetime] = mapped_column(default=utcnow)

    generation: Mapped[Generation] = relationship(back_populates="images")


class ApplicationSetting(Base):
    __tablename__ = "application_settings"

    key: Mapped[str] = mapped_column(String(128), primary_key=True)
    value: Mapped[dict[str, Any]] = mapped_column(JSON)
    updated_at: Mapped[datetime] = mapped_column(default=utcnow, onupdate=utcnow)
