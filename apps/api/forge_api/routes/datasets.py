from fastapi import APIRouter, UploadFile, status
from fastapi.responses import FileResponse

from forge_api.dependencies import DbDep, ServicesDep
from forge_api.errors import NotFoundError, UnprocessableError
from forge_api.schemas.datasets import (
    CaptionUpdate,
    DatasetCreate,
    DatasetImageOut,
    DatasetOut,
    DatasetSummary,
    DatasetUpdate,
    ReorderRequest,
    UploadResult,
)
from forge_api.services import dataset_service

router = APIRouter(prefix="/api/datasets", tags=["datasets"])

_MEDIA_TYPES = {"PNG": "image/png", "JPEG": "image/jpeg", "WEBP": "image/webp"}


@router.get("", response_model=list[DatasetSummary])
def list_datasets(db: DbDep) -> list[DatasetSummary]:
    return dataset_service.list_datasets(db)


@router.post("", response_model=DatasetOut, status_code=status.HTTP_201_CREATED)
def create_dataset(body: DatasetCreate, db: DbDep) -> DatasetOut:
    return dataset_service.dataset_out(dataset_service.create_dataset(db, body))


@router.get("/{dataset_id}", response_model=DatasetOut)
def get_dataset(dataset_id: int, db: DbDep) -> DatasetOut:
    return dataset_service.dataset_out(dataset_service.get_dataset(db, dataset_id))


@router.patch("/{dataset_id}", response_model=DatasetOut)
def update_dataset(dataset_id: int, body: DatasetUpdate, db: DbDep) -> DatasetOut:
    return dataset_service.dataset_out(dataset_service.update_dataset(db, dataset_id, body))


@router.delete("/{dataset_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_dataset(dataset_id: int, db: DbDep, services: ServicesDep) -> None:
    dataset_service.delete_dataset(db, services.settings, dataset_id)


@router.post("/{dataset_id}/images", response_model=UploadResult)
def upload_images(
    dataset_id: int, files: list[UploadFile], db: DbDep, services: ServicesDep
) -> UploadResult:
    if len(files) > dataset_service.MAX_FILES_PER_UPLOAD:
        raise UnprocessableError(
            f"Upload at most {dataset_service.MAX_FILES_PER_UPLOAD} files at a time."
        )
    return dataset_service.upload_images(
        db, services.settings, dataset_id, [(f.filename or "", f.file) for f in files]
    )


@router.put("/{dataset_id}/order", response_model=DatasetOut)
def reorder(dataset_id: int, body: ReorderRequest, db: DbDep) -> DatasetOut:
    return dataset_service.dataset_out(dataset_service.reorder(db, dataset_id, body.image_ids))


@router.patch("/{dataset_id}/images/{image_id}", response_model=DatasetImageOut)
def update_caption(
    dataset_id: int, image_id: int, body: CaptionUpdate, db: DbDep
) -> DatasetImageOut:
    return dataset_service.update_caption(db, dataset_id, image_id, body.caption)


@router.delete("/{dataset_id}/images/{image_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_image(dataset_id: int, image_id: int, db: DbDep, services: ServicesDep) -> None:
    dataset_service.delete_image(db, services.settings, dataset_id, image_id)


# Files are addressed by database ids only, so clients can never name an arbitrary path.
@router.get("/{dataset_id}/images/{image_id}/file")
def image_file(dataset_id: int, image_id: int, db: DbDep, services: ServicesDep) -> FileResponse:
    image = dataset_service.get_image(db, dataset_id, image_id)
    path = dataset_service.image_path(services.settings, dataset_id, image.stored_filename)
    if not path.is_file():
        raise NotFoundError("Image file is missing.")
    return FileResponse(path, media_type=_MEDIA_TYPES[image.format])


@router.get("/{dataset_id}/images/{image_id}/thumbnail")
def thumbnail_file(
    dataset_id: int, image_id: int, db: DbDep, services: ServicesDep
) -> FileResponse:
    image = dataset_service.get_image(db, dataset_id, image_id)
    path = dataset_service.thumbnail_path(services.settings, dataset_id, image.stored_filename)
    if not path.is_file():
        raise NotFoundError("Thumbnail is missing.")
    return FileResponse(path, media_type="image/webp")
