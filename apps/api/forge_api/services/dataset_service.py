"""Datasets of training images: storage, validated uploads, captions, ordering and quality flags."""

import logging
import re
import shutil
import uuid
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path
from typing import BinaryIO

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from forge_api.config import Settings
from forge_api.db.models import Dataset, DatasetImage
from forge_api.errors import NotFoundError, UnprocessableError
from forge_api.schemas.datasets import (
    DatasetCreate,
    DatasetImageOut,
    DatasetOut,
    DatasetSummary,
    DatasetUpdate,
    SkippedUpload,
    UploadResult,
)
from forge_api.services import image_analysis
from forge_api.services.storage import resolve_within

logger = logging.getLogger(__name__)

MAX_IMAGES_PER_DATASET = 1000
MAX_FILES_PER_UPLOAD = 50
_CHUNK_SIZE = 1024 * 1024


# ---- paths ------------------------------------------------------------------------------


def dataset_dir(settings: Settings, dataset_id: int) -> Path:
    return resolve_within(settings.dataset_directory, str(dataset_id))


# Paths take the dataset id explicitly: a newly added image has no dataset_id until flushed.
def image_path(settings: Settings, dataset_id: int, stored_filename: str) -> Path:
    return resolve_within(dataset_dir(settings, dataset_id), f"images/{stored_filename}")


def thumbnail_path(settings: Settings, dataset_id: int, stored_filename: str) -> Path:
    stem = Path(stored_filename).stem
    return resolve_within(dataset_dir(settings, dataset_id), f"thumbs/{stem}.webp")


# ---- datasets ---------------------------------------------------------------------------


def create_dataset(db: Session, body: DatasetCreate) -> Dataset:
    dataset = Dataset(
        name=body.name, description=body.description, target_resolution=body.target_resolution
    )
    db.add(dataset)
    db.commit()
    logger.info("dataset_created", extra={"dataset_id": dataset.id})
    return dataset


def get_dataset(db: Session, dataset_id: int) -> Dataset:
    dataset = db.scalar(
        select(Dataset).where(Dataset.id == dataset_id).options(selectinload(Dataset.images))
    )
    if dataset is None:
        raise NotFoundError("Dataset not found.")
    return dataset


def list_datasets(db: Session) -> list[DatasetSummary]:
    datasets = db.scalars(
        select(Dataset).options(selectinload(Dataset.images)).order_by(Dataset.id.desc())
    )
    return [summarize(d) for d in datasets]


def update_dataset(db: Session, dataset_id: int, changes: DatasetUpdate) -> Dataset:
    dataset = get_dataset(db, dataset_id)
    for field, value in changes.model_dump(exclude_unset=True).items():
        if value is None:
            raise UnprocessableError(f"'{field}' cannot be null.")
        setattr(dataset, field, value)
    db.commit()
    return dataset


def delete_dataset(db: Session, settings: Settings, dataset_id: int) -> None:
    dataset = get_dataset(db, dataset_id)
    folder = dataset_dir(settings, dataset.id)
    db.delete(dataset)
    db.commit()
    if folder.exists():
        shutil.rmtree(folder)
    logger.info("dataset_deleted", extra={"dataset_id": dataset_id})


# ---- images -----------------------------------------------------------------------------


def upload_images(
    db: Session,
    settings: Settings,
    dataset_id: int,
    files: Iterable[tuple[str, BinaryIO]],
) -> UploadResult:
    """Validate and add images. Invalid files and exact duplicates are skipped, not fatal."""
    dataset = get_dataset(db, dataset_id)
    known = {image.sha256: image.original_filename for image in dataset.images}
    next_position = max((image.position for image in dataset.images), default=-1) + 1
    added: list[DatasetImage] = []
    skipped: list[SkippedUpload] = []
    written: list[Path] = []

    try:
        for raw_name, stream in files:
            name = display_filename(raw_name)
            if len(dataset.images) >= MAX_IMAGES_PER_DATASET:
                skipped.append(_skip(name, "dataset_full", "The dataset is full."))
                continue
            data = _read_limited(stream, settings.max_image_upload_bytes)
            if data is None:
                limit = settings.max_image_upload_mb
                skipped.append(_skip(name, "too_large", f"Larger than the {limit} MB limit."))
                continue
            try:
                facts = image_analysis.analyse(data)
            except image_analysis.InvalidImageError as exc:
                skipped.append(_skip(name, exc.reason, exc.message))
                continue
            if facts.sha256 in known:
                skipped.append(_skip(name, "duplicate", f"Same file as {known[facts.sha256]}."))
                continue

            image = DatasetImage(
                position=next_position,
                original_filename=name,
                stored_filename=f"{uuid.uuid4().hex}{facts.extension}",
                format=facts.format,
                width=facts.width,
                height=facts.height,
                file_size_bytes=len(data),
                sha256=facts.sha256,
                perceptual_hash=facts.perceptual_hash,
                blur_score=facts.blur_score,
                caption="",
            )
            dataset.images.append(image)
            written += _write_files(settings, dataset.id, image.stored_filename, data)
            known[facts.sha256] = name
            next_position += 1
            added.append(image)
        db.commit()
    except Exception:
        # Keep disk and database consistent: nothing from a failed batch is left behind.
        db.rollback()
        for path in written:
            path.unlink(missing_ok=True)
        raise

    logger.info(
        "dataset_images_uploaded",
        extra={"dataset_id": dataset_id, "added": len(added), "skipped": len(skipped)},
    )
    flags = compute_flags(dataset)
    return UploadResult(added=[image_out(i, flags) for i in added], skipped=skipped)


def update_caption(db: Session, dataset_id: int, image_id: int, caption: str) -> DatasetImageOut:
    image = get_image(db, dataset_id, image_id)
    image.caption = caption.strip()
    image.caption_source = "manual"
    image.caption_updated_at = datetime.now(UTC)
    db.commit()
    return image_out(image, compute_flags(image.dataset))


def delete_image(db: Session, settings: Settings, dataset_id: int, image_id: int) -> None:
    image = get_image(db, dataset_id, image_id)
    files = [
        image_path(settings, dataset_id, image.stored_filename),
        thumbnail_path(settings, dataset_id, image.stored_filename),
    ]
    dataset = image.dataset
    dataset.images.remove(image)
    for position, remaining in enumerate(dataset.images):
        remaining.position = position
    db.commit()
    for path in files:
        path.unlink(missing_ok=True)


def reorder(db: Session, dataset_id: int, image_ids: list[int]) -> Dataset:
    dataset = get_dataset(db, dataset_id)
    by_id = {image.id: image for image in dataset.images}
    if len(image_ids) != len(by_id) or set(image_ids) != set(by_id):
        raise UnprocessableError("The new order must list every image in the dataset exactly once.")
    for position, image_id in enumerate(image_ids):
        by_id[image_id].position = position
    db.commit()
    db.refresh(dataset)  # re-sort the relationship by the new positions
    return dataset


def get_image(db: Session, dataset_id: int, image_id: int) -> DatasetImage:
    image = db.get(DatasetImage, image_id)
    if image is None or image.dataset_id != dataset_id:
        raise NotFoundError("Image not found.")
    return image


# ---- read models ------------------------------------------------------------------------

Flags = dict[int, tuple[list[str], list[int]]]


def compute_flags(dataset: Dataset) -> Flags:
    """Quality flags per image id, plus the ids of visually near-identical images."""
    images = dataset.images
    near: dict[int, list[int]] = {image.id: [] for image in images}
    # Pairwise comparison is fine at MAX_IMAGES_PER_DATASET scale (~500k cheap XOR/popcounts).
    for i, first in enumerate(images):
        for second in images[i + 1 :]:
            distance = image_analysis.hamming_distance(
                first.perceptual_hash, second.perceptual_hash
            )
            if distance <= image_analysis.NEAR_DUPLICATE_BITS:
                near[first.id].append(second.id)
                near[second.id].append(first.id)
    result: Flags = {}
    for image in images:
        flags = image_analysis.quality_flags(
            image.width, image.height, image.blur_score, dataset.target_resolution
        )
        if near[image.id]:
            flags.append("near_duplicate")
        result[image.id] = (flags, near[image.id])
    return result


def image_out(image: DatasetImage, flags: Flags) -> DatasetImageOut:
    image_flags, near_duplicates = flags.get(image.id, ([], []))
    return DatasetImageOut.model_validate(
        {
            **{c: getattr(image, c) for c in DatasetImageOut.model_fields if hasattr(image, c)},
            "flags": image_flags,
            "near_duplicate_of": near_duplicates,
        }
    )


def summarize(dataset: Dataset) -> DatasetSummary:
    flags = compute_flags(dataset)
    cover = dataset.images[0] if dataset.images else None
    return DatasetSummary(
        id=dataset.id,
        name=dataset.name,
        description=dataset.description,
        target_resolution=dataset.target_resolution,
        created_at=dataset.created_at,
        updated_at=dataset.updated_at,
        image_count=len(dataset.images),
        flagged_count=sum(1 for image_flags, _ in flags.values() if image_flags),
        uncaptioned_count=sum(1 for image in dataset.images if not image.caption),
        cover_thumbnail_url=(
            f"/api/datasets/{dataset.id}/images/{cover.id}/thumbnail" if cover else None
        ),
    )


def dataset_out(dataset: Dataset) -> DatasetOut:
    flags = compute_flags(dataset)
    return DatasetOut(
        **summarize(dataset).model_dump(),
        images=[image_out(image, flags) for image in dataset.images],
    )


# ---- helpers ----------------------------------------------------------------------------


def display_filename(raw: str) -> str:
    """Basename for display only (never used as a path); clients may send full paths."""
    name = re.split(r"[\\/]", raw or "")[-1].strip()
    return name[:255] or "image"


def _skip(filename: str, reason: str, message: str) -> SkippedUpload:
    return SkippedUpload.model_validate(
        {"filename": filename, "reason": reason, "message": message}
    )


def _read_limited(stream: BinaryIO, max_bytes: int) -> bytes | None:
    """Read the whole upload, or return None as soon as it exceeds the limit."""
    chunks: list[bytes] = []
    size = 0
    while chunk := stream.read(_CHUNK_SIZE):
        size += len(chunk)
        if size > max_bytes:
            return None
        chunks.append(chunk)
    return b"".join(chunks)


def _write_files(
    settings: Settings, dataset_id: int, stored_filename: str, data: bytes
) -> list[Path]:
    written: list[Path] = []
    for path, content in (
        (image_path(settings, dataset_id, stored_filename), data),
        (
            thumbnail_path(settings, dataset_id, stored_filename),
            image_analysis.make_thumbnail(data),
        ),
    ):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        written.append(path)
    return written
