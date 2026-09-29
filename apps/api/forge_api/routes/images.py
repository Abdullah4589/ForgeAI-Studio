from fastapi import APIRouter
from fastapi.responses import FileResponse

from forge_api.dependencies import DbDep, ServicesDep
from forge_api.services import history_service

router = APIRouter(prefix="/api/images", tags=["images"])


@router.get("/{image_id}")
def get_image(
    image_id: int, db: DbDep, services: ServicesDep, download: bool = False
) -> FileResponse:
    # Images are addressed by DB id only, so clients can never name an arbitrary file path.
    path = history_service.image_file(db, services.settings.output_directory, image_id)
    return FileResponse(
        path,
        media_type="image/png",
        filename=f"forge-{image_id}.png" if download else None,
        content_disposition_type="attachment" if download else "inline",
    )
