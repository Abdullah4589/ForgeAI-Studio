"""AI captioning of dataset images: target selection, the background job, and persistence.

Kept separate from dataset management and (future) training: it only reads images and writes
captions through the rules below.
"""

import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from functools import partial
from typing import Any, Literal

from PIL import Image, ImageOps, UnidentifiedImageError

from ai.captioning.cleanup import clean_caption
from ai.errors import GenerationCancelledError
from forge_api.container import AppServices
from forge_api.db.models import DatasetImage
from forge_api.errors import UnprocessableError
from forge_api.jobs.manager import JobContext, JobSnapshot
from forge_api.schemas.captions import CaptionRequest, OverwriteMode
from forge_api.services import dataset_service, generation_service

logger = logging.getLogger(__name__)

JOB_KIND = "captioning"


def should_caption(image: DatasetImage, mode: OverwriteMode) -> bool:
    """The single rule for what an AI run may write over."""
    if not image.caption:
        return True
    if image.caption_source == "ai":
        return mode in ("replace_ai", "everything")
    # Manual captions (or any caption of unknown origin) need the explicit "everything" mode.
    return mode == "everything"


@dataclass(frozen=True)
class CaptionPlan:
    image_ids: list[int]
    skipped_manual: int
    skipped_existing: int


def plan(images: list[DatasetImage], mode: OverwriteMode) -> CaptionPlan:
    targets: list[int] = []
    skipped_manual = skipped_existing = 0
    for image in images:
        if should_caption(image, mode):
            targets.append(image.id)
        elif image.caption_source == "ai":
            skipped_existing += 1
        else:
            skipped_manual += 1
    return CaptionPlan(targets, skipped_manual, skipped_existing)


def start_captioning(
    services: AppServices, dataset_id: int, request: CaptionRequest
) -> tuple[JobSnapshot, CaptionPlan]:
    with services.session_factory() as db:
        dataset = dataset_service.get_dataset(db, dataset_id)
        images = dataset.images
        if request.image_ids is not None:
            by_id = {image.id: image for image in images}
            missing = [i for i in request.image_ids if i not in by_id]
            if missing:
                raise UnprocessableError("Some images are not part of this dataset.")
            images = [by_id[i] for i in dict.fromkeys(request.image_ids)]
        captions = plan(images, request.overwrite)
    if not captions.image_ids:
        raise UnprocessableError("No images need captions with these settings.")
    generation_service.ensure_idle(services)
    job = services.jobs.submit(
        JOB_KIND, partial(_run, services, dataset_id, captions.image_ids, request.overwrite)
    )
    logger.info(
        "captioning_requested",
        extra={
            "job_id": job.id,
            "dataset_id": dataset_id,
            "images": len(captions.image_ids),
            "overwrite": request.overwrite,
        },
    )
    return job, captions


def _run(
    services: AppServices,
    dataset_id: int,
    image_ids: list[int],
    mode: OverwriteMode,
    ctx: JobContext,
) -> dict[str, Any]:
    # Never hold the image-generation model and the captioner in memory at the same time.
    services.backend.release()
    total = len(image_ids)
    counts = {"captioned": 0, "skipped": 0, "failed": 0}
    for index, image_id in enumerate(image_ids):
        if ctx.cancel_event.is_set():
            raise GenerationCancelledError("Captioning was cancelled.")
        counts[_caption_one(services, dataset_id, image_id, mode, ctx, index, total)] += 1
        ctx.report_progress(index + 1, total, f"Captioned {index + 1} of {total}")
    logger.info("captioning_completed", extra={"dataset_id": dataset_id, **counts})
    return {"dataset_id": dataset_id, **counts}


def _caption_one(
    services: AppServices,
    dataset_id: int,
    image_id: int,
    mode: OverwriteMode,
    ctx: JobContext,
    index: int,
    total: int,
) -> Literal["captioned", "skipped", "failed"]:
    with services.session_factory() as db:
        image = db.get(DatasetImage, image_id)
        # Re-check now: the image may have been removed, or captioned by hand, since queueing.
        if image is None or image.dataset_id != dataset_id or not should_caption(image, mode):
            return "skipped"
        name = image.original_filename
        ctx.report_progress(index, total, f"Captioning {name} ({index + 1} of {total})")
        try:
            picture = _load_image(services, image)
        except (OSError, UnidentifiedImageError):
            logger.exception("caption_image_unreadable", extra={"image_id": image_id})
            return "failed"
        text = clean_caption(services.captioner.caption(picture))
        # Re-read in case the user edited this caption while the model was running.
        db.refresh(image)
        if not should_caption(image, mode):
            return "skipped"
        image.caption = text
        image.caption_source = "ai"
        image.caption_model = services.captioner.name
        image.caption_updated_at = datetime.now(UTC)
        db.commit()
        return "captioned"


def _load_image(services: AppServices, image: DatasetImage) -> Image.Image:
    path = dataset_service.image_path(services.settings, image.dataset_id, image.stored_filename)
    with Image.open(path) as opened:
        return ImageOps.exif_transpose(opened).convert("RGB")
