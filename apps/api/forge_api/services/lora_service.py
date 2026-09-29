"""LoRA catalogue: directory sync, validated import, metadata edits and deletion."""

import logging
import os
import uuid
from pathlib import Path
from typing import BinaryIO

from sqlalchemy import select
from sqlalchemy.orm import Session

from ai.errors import AIError, IncompatibleLoraError
from ai.lora.inspect import inspect_lora, is_compatible
from forge_api.db.models import DiffusionModel, Lora
from forge_api.errors import ConflictError, NotFoundError, PayloadTooLargeError, UnprocessableError
from forge_api.schemas.loras import LoraUpdate
from forge_api.services.storage import resolve_within, safe_filename

logger = logging.getLogger(__name__)

LORA_SUFFIX = ".safetensors"
_CHUNK_SIZE = 1024 * 1024


def sync_loras(db: Session, lora_directory: Path) -> None:
    existing = {lora.filename: lora for lora in db.scalars(select(Lora))}
    on_disk: set[str] = set()
    if lora_directory.is_dir():
        for path in sorted(lora_directory.glob(f"*{LORA_SUFFIX}")):
            on_disk.add(path.name)
            record = existing.get(path.name)
            if record is not None:
                record.available = True
                continue
            try:
                info = inspect_lora(path)
            except AIError as exc:
                logger.warning("lora_skipped", extra={"file": path.name, "reason": exc.message})
                continue
            db.add(
                Lora(
                    name=path.stem,
                    filename=path.name,
                    file_size_bytes=path.stat().st_size,
                    base_architecture=info.architecture,
                    rank=info.rank,
                )
            )
    for filename, record in existing.items():
        if filename not in on_disk:
            record.available = False
    db.commit()


def list_loras(db: Session) -> list[Lora]:
    return list(db.scalars(select(Lora).order_by(Lora.name)))


def get_lora(db: Session, lora_id: int) -> Lora:
    record = db.get(Lora, lora_id)
    if record is None:
        raise NotFoundError("LoRA not found.")
    return record


def import_lora(
    db: Session,
    lora_directory: Path,
    original_filename: str,
    stream: BinaryIO,
    max_bytes: int,
) -> Lora:
    filename = safe_filename(original_filename, required_suffix=LORA_SUFFIX)
    destination = resolve_within(lora_directory, filename)
    if destination.exists() or db.scalar(select(Lora).where(Lora.filename == filename)):
        raise ConflictError(f"A LoRA named '{filename}' already exists.")

    # Write to a temp name first so a partial or invalid upload never appears as a LoRA.
    temp_path = resolve_within(lora_directory, f".upload-{uuid.uuid4().hex}.part")
    try:
        size = _copy_limited(stream, temp_path, max_bytes)
        info = inspect_lora(temp_path)
        os.replace(temp_path, destination)
    finally:
        temp_path.unlink(missing_ok=True)

    record = Lora(
        name=Path(filename).stem,
        filename=filename,
        file_size_bytes=size,
        base_architecture=info.architecture,
        rank=info.rank,
    )
    db.add(record)
    db.commit()
    logger.info(
        "lora_imported",
        extra={"file": filename, "bytes": size, "architecture": info.architecture},
    )
    return record


def update_lora(db: Session, lora_id: int, changes: LoraUpdate) -> Lora:
    record = get_lora(db, lora_id)
    for field, value in changes.model_dump(exclude_unset=True).items():
        if value is None:
            raise UnprocessableError(f"'{field}' cannot be null.")
        setattr(record, field, value)
    db.commit()
    return record


def delete_lora(db: Session, lora_directory: Path, lora_id: int) -> None:
    record = get_lora(db, lora_id)
    resolve_within(lora_directory, record.filename).unlink(missing_ok=True)
    db.delete(record)
    db.commit()
    logger.info("lora_deleted", extra={"file": record.filename})


def require_usable_with(lora: Lora, model: DiffusionModel) -> None:
    if not lora.available:
        raise UnprocessableError("This LoRA's file is missing from the LoRA directory.")
    if not lora.enabled:
        raise UnprocessableError("This LoRA is disabled. Enable it on the LoRAs page first.")
    if not is_compatible(lora.base_architecture, model.architecture):
        raise IncompatibleLoraError(
            f"'{lora.name}' was trained for {lora.base_architecture} and can't be used with "
            f"'{model.name}' ({model.architecture})."
        )


def _copy_limited(stream: BinaryIO, destination: Path, max_bytes: int) -> int:
    written = 0
    with destination.open("wb") as out:
        while chunk := stream.read(_CHUNK_SIZE):
            written += len(chunk)
            if written > max_bytes:
                raise PayloadTooLargeError(
                    f"File is larger than the {max_bytes // (1024 * 1024)} MB upload limit."
                )
            out.write(chunk)
    if written == 0:
        raise UnprocessableError("The uploaded file is empty.")
    return written
