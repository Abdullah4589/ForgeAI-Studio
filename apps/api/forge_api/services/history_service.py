"""Querying and deleting stored generations and their image files."""

import logging
from pathlib import Path

from sqlalchemy import ColumnElement, func, select
from sqlalchemy.orm import Session, selectinload

from forge_api.db.models import Generation, GenerationImage
from forge_api.errors import NotFoundError
from forge_api.schemas.history import SortOrder
from forge_api.services.storage import resolve_within

logger = logging.getLogger(__name__)


def list_history(
    db: Session,
    *,
    query: str | None,
    model_id: int | None,
    lora_id: int | None,
    sort: SortOrder,
    page: int,
    page_size: int,
) -> tuple[list[Generation], int]:
    filters: list[ColumnElement[bool]] = []
    if query:
        # Escape LIKE wildcards so user text is matched literally (value is still bound).
        escaped = query.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        pattern = f"%{escaped}%"
        filters.append(
            Generation.prompt.ilike(pattern, escape="\\")
            | Generation.negative_prompt.ilike(pattern, escape="\\")
        )
    if model_id is not None:
        filters.append(Generation.model_id == model_id)
    if lora_id is not None:
        filters.append(Generation.lora_id == lora_id)

    total = db.scalar(select(func.count()).select_from(Generation).where(*filters)) or 0
    order = Generation.id.desc() if sort == "newest" else Generation.id.asc()
    items = db.scalars(
        select(Generation)
        .where(*filters)
        .options(selectinload(Generation.images))
        .order_by(order)
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return list(items), total


def get_generation(db: Session, generation_id: int) -> Generation:
    generation = db.scalar(
        select(Generation)
        .where(Generation.id == generation_id)
        .options(selectinload(Generation.images))
    )
    if generation is None:
        raise NotFoundError("Generation not found.")
    return generation


def delete_generation(db: Session, output_dir: Path, generation_id: int) -> None:
    generation = get_generation(db, generation_id)
    files = [image.file_path for image in generation.images]
    db.delete(generation)
    db.commit()
    for relative in files:
        _remove_file(output_dir, relative)
    logger.info("generation_deleted", extra={"generation_id": generation_id})


def delete_image(db: Session, output_dir: Path, image_id: int) -> None:
    image = _get_image(db, image_id)
    generation = image.generation
    relative = image.file_path
    db.delete(image)
    db.flush()
    db.refresh(generation)
    # A history entry without images has nothing left to show or reuse.
    if not generation.images:
        db.delete(generation)
    db.commit()
    _remove_file(output_dir, relative)


def image_file(db: Session, output_dir: Path, image_id: int) -> Path:
    path = resolve_within(output_dir, _get_image(db, image_id).file_path)
    if not path.is_file():
        raise NotFoundError("Image file is missing.")
    return path


def _get_image(db: Session, image_id: int) -> GenerationImage:
    image = db.get(GenerationImage, image_id)
    if image is None:
        raise NotFoundError("Image not found.")
    return image


def _remove_file(output_dir: Path, relative: str) -> None:
    try:
        resolve_within(output_dir, relative).unlink(missing_ok=True)
    except OSError:
        # The DB row is already gone; a leftover file is harmless but worth knowing about.
        logger.exception("image_file_delete_failed", extra={"file": relative})
