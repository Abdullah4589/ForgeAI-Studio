"""Model catalogue (DB) kept in sync with the model directory, plus load/unload."""

import logging
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from ai.generation.types import ModelRef
from ai.model_manager.discovery import scan_models
from ai.pipelines.registry import get_spec
from forge_api.container import AppServices
from forge_api.db.models import DiffusionModel
from forge_api.errors import ConflictError, NotFoundError, UnprocessableError
from forge_api.schemas.models import ModelOut
from forge_api.services.storage import resolve_within

logger = logging.getLogger(__name__)


def sync_models(db: Session, model_directory: Path) -> None:
    discovered = {m.path.name: m for m in scan_models(model_directory)}
    existing = {m.path: m for m in db.scalars(select(DiffusionModel))}

    for rel_path, found in discovered.items():
        resolutions = [list(r) for r in found.supported_resolutions]
        record = existing.get(rel_path)
        if record is None:
            db.add(
                DiffusionModel(
                    name=found.name,
                    path=rel_path,
                    source_type=found.source_type,
                    architecture=found.architecture,
                    file_size_bytes=found.size_bytes,
                    supported_resolutions=resolutions,
                )
            )
        else:
            record.available = True
            record.source_type = found.source_type
            record.architecture = found.architecture
            record.file_size_bytes = found.size_bytes
            record.supported_resolutions = resolutions
    for rel_path, record in existing.items():
        if rel_path not in discovered:
            record.available = False
    db.commit()
    logger.info("models_synced", extra={"count": len(discovered)})


def list_models(db: Session, services: AppServices) -> list[ModelOut]:
    loaded_path = _loaded_path(services)
    records = db.scalars(select(DiffusionModel).order_by(DiffusionModel.name))
    return [
        ModelOut.model_validate(r).model_copy(
            update={"loaded": loaded_path == model_path(services, r)}
        )
        for r in records
    ]


def get_model(db: Session, model_id: int) -> DiffusionModel:
    record = db.get(DiffusionModel, model_id)
    if record is None:
        raise NotFoundError("Model not found.")
    return record


def require_usable(record: DiffusionModel) -> None:
    if not record.available:
        raise UnprocessableError("This model's files are missing from the model directory.")
    if get_spec(record.architecture) is None:
        raise UnprocessableError(
            f"'{record.name}' has an unrecognised architecture and can't be used yet."
        )


def model_path(services: AppServices, record: DiffusionModel) -> Path:
    return resolve_within(services.settings.model_directory, record.path)


def model_ref(services: AppServices, record: DiffusionModel) -> ModelRef:
    return ModelRef(
        path=model_path(services, record),
        source_type="diffusers" if record.source_type == "diffusers" else "single_file",
        architecture=record.architecture,
    )


def load_model(db: Session, services: AppServices, model_id: int) -> None:
    if services.settings.generation_backend == "mock":
        raise ConflictError("Model loading is not available while the mock backend is active.")
    record = get_model(db, model_id)
    require_usable(record)
    services.backend.preload(model_ref(services, record))


def unload_model(services: AppServices) -> None:
    services.backend.release()


def loaded_model_id(db: Session, services: AppServices) -> int | None:
    loaded_path = _loaded_path(services)
    if loaded_path is None:
        return None
    for record in db.scalars(select(DiffusionModel)):
        if model_path(services, record) == loaded_path:
            return record.id
    return None


def _loaded_path(services: AppServices) -> Path | None:
    request = services.model_manager.loaded_request()
    return request.path.resolve() if request else None
