from fastapi import APIRouter, status

from forge_api.dependencies import ServicesDep
from forge_api.schemas.captions import CaptionJobOut, CaptionRequest
from forge_api.schemas.generation import JobOut
from forge_api.services import caption_service

router = APIRouter(prefix="/api/datasets", tags=["captions"])


@router.post(
    "/{dataset_id}/captions", response_model=CaptionJobOut, status_code=status.HTTP_202_ACCEPTED
)
def generate_captions(
    dataset_id: int, body: CaptionRequest, services: ServicesDep
) -> CaptionJobOut:
    """Queue AI captioning. Progress and cancellation use the generic /api/jobs endpoints."""
    job, captions = caption_service.start_captioning(services, dataset_id, body)
    return CaptionJobOut(
        **JobOut.model_validate(job, from_attributes=True).model_dump(),
        queued=len(captions.image_ids),
        skipped_manual=captions.skipped_manual,
        skipped_existing=captions.skipped_existing,
    )
