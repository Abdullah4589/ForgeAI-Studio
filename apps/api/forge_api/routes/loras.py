from fastapi import APIRouter, Request, UploadFile, status

from forge_api.db.models import Lora
from forge_api.dependencies import DbDep, ServicesDep
from forge_api.errors import PayloadTooLargeError, UnprocessableError
from forge_api.schemas.loras import LoraOut, LoraUpdate
from forge_api.services import lora_service

router = APIRouter(prefix="/api/loras", tags=["loras"])

# Multipart framing adds a little on top of the file itself.
_MULTIPART_OVERHEAD_BYTES = 1024 * 1024


@router.get("", response_model=list[LoraOut])
def list_loras(db: DbDep) -> list[Lora]:
    return lora_service.list_loras(db)


@router.post("/rescan", response_model=list[LoraOut])
def rescan_loras(db: DbDep, services: ServicesDep) -> list[Lora]:
    lora_service.sync_loras(db, services.settings.lora_directory)
    return lora_service.list_loras(db)


@router.post("/import", response_model=LoraOut, status_code=status.HTTP_201_CREATED)
def import_lora(request: Request, file: UploadFile, db: DbDep, services: ServicesDep) -> Lora:
    max_bytes = services.settings.max_upload_bytes
    declared = request.headers.get("content-length", "")
    # Cheap early rejection; the streamed copy enforces the limit again on the actual bytes.
    if declared.isdigit() and int(declared) > max_bytes + _MULTIPART_OVERHEAD_BYTES:
        raise PayloadTooLargeError(
            f"File is larger than the {services.settings.max_upload_size_mb} MB upload limit."
        )
    if not file.filename:
        raise UnprocessableError("A file name is required.")
    return lora_service.import_lora(
        db, services.settings.lora_directory, file.filename, file.file, max_bytes
    )


@router.patch("/{lora_id}", response_model=LoraOut)
def update_lora(lora_id: int, body: LoraUpdate, db: DbDep) -> Lora:
    return lora_service.update_lora(db, lora_id, body)


@router.delete("/{lora_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_lora(lora_id: int, db: DbDep, services: ServicesDep) -> None:
    lora_service.delete_lora(db, services.settings.lora_directory, lora_id)
