"""Validates generation requests, queues them, and persists results to history."""

import logging
import secrets
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from functools import partial
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from ai.generation.types import (
    MAX_SEED,
    CancelToken,
    GenerationOutput,
    GenerationParams,
    LoraRef,
    ProgressCallback,
)
from forge_api.container import AppServices
from forge_api.db.models import DiffusionModel, Generation, GenerationImage
from forge_api.errors import ConflictError
from forge_api.jobs.manager import JobContext, JobSnapshot
from forge_api.logging_config import truncate
from forge_api.schemas.generation import GenerateRequest
from forge_api.services import lora_service, model_service
from forge_api.services.storage import resolve_within

logger = logging.getLogger(__name__)

JOB_KIND = "generation"


@dataclass(frozen=True)
class HistoryLabels:
    """Names captured at request time so history stays readable if the model/LoRA is removed."""

    model_id: int
    model_name: str
    lora_id: int | None
    lora_name: str | None


@dataclass(frozen=True)
class PreparedGeneration:
    """A fully validated generation, ready to run without touching the request DB session."""

    params: GenerationParams
    labels: HistoryLabels


@dataclass(frozen=True)
class ComparisonCell:
    comparison_id: int
    index: int


def resolve_seed(seed: int | None) -> int:
    # Always resolve the seed up front so every result can be reproduced from history.
    return seed if seed is not None else secrets.randbelow(MAX_SEED + 1)


def ensure_idle(services: AppServices) -> None:
    # One job at a time keeps memory predictable and makes Cancel unambiguous in the UI.
    if services.jobs.active_job() is not None:
        raise ConflictError(
            "Another job (generation, comparison or captioning) is running. "
            "Wait for it or cancel it."
        )


def prepare(
    db: Session,
    services: AppServices,
    *,
    model: DiffusionModel,
    request: GenerateRequest,
    seed: int,
) -> PreparedGeneration:
    """Check the model and LoRA can be used together and build the generation parameters."""
    model_service.require_usable(model)
    lora_ref: LoraRef | None = None
    lora_name: str | None = None
    if request.lora_id is not None:
        lora = lora_service.get_lora(db, request.lora_id)
        lora_service.require_usable_with(lora, model)
        lora_ref = LoraRef(
            path=resolve_within(services.settings.lora_directory, lora.filename),
            strength=request.lora_strength,
        )
        lora_name = lora.name

    params = GenerationParams(
        model=model_service.model_ref(services, model),
        prompt=request.prompt,
        negative_prompt=request.negative_prompt,
        width=request.width,
        height=request.height,
        steps=request.steps,
        guidance_scale=request.guidance_scale,
        seed=seed,
        num_images=request.num_images,
        lora=lora_ref,
    )
    return PreparedGeneration(
        params, HistoryLabels(model.id, model.name, request.lora_id, lora_name)
    )


def start_generation(db: Session, services: AppServices, request: GenerateRequest) -> JobSnapshot:
    model = model_service.get_model(db, request.model_id)
    prepared = prepare(db, services, model=model, request=request, seed=resolve_seed(request.seed))
    ensure_idle(services)
    job = services.jobs.submit(JOB_KIND, partial(_run_generation, services, prepared))
    params = prepared.params
    logger.info(
        "generation_requested",
        extra={
            "job_id": job.id,
            "model": model.name,
            "lora": prepared.labels.lora_name,
            "prompt": truncate(params.prompt),
            "size": f"{params.width}x{params.height}",
            "steps": params.steps,
            "num_images": params.num_images,
            "seed": params.seed,
        },
    )
    return job


def cancel_generation(services: AppServices, job_id: str) -> JobSnapshot | None:
    return services.jobs.cancel(job_id)


def execute(
    services: AppServices,
    prepared: PreparedGeneration,
    on_progress: ProgressCallback,
    cancel: CancelToken,
    cell: ComparisonCell | None = None,
) -> int:
    """Run the backend and store the result in history. Returns the generation id."""
    started = time.perf_counter()
    output = services.backend.generate(prepared.params, on_progress, cancel)
    duration_ms = round((time.perf_counter() - started) * 1000)
    generation_id = _persist(services, prepared, output, duration_ms, cell)
    logger.info(
        "generation_completed",
        extra={"generation_id": generation_id, "duration_ms": duration_ms, "device": output.device},
    )
    return generation_id


def _run_generation(
    services: AppServices, prepared: PreparedGeneration, ctx: JobContext
) -> dict[str, Any]:
    steps = prepared.params.steps
    ctx.report_progress(0, steps, "Preparing model")

    def on_progress(step: int, total: int) -> None:
        ctx.report_progress(step, total, f"Step {step} of {total}")

    generation_id = execute(services, prepared, on_progress, ctx.cancel_event)
    return {"generation_id": generation_id}


def _persist(
    services: AppServices,
    prepared: PreparedGeneration,
    output: GenerationOutput,
    duration_ms: int,
    cell: ComparisonCell | None,
) -> int:
    params, labels = prepared.params, prepared.labels
    output_dir = services.settings.output_directory
    day_folder = datetime.now(UTC).strftime("%Y-%m-%d")
    written: list[Path] = []
    with services.session_factory() as db:
        try:
            generation = Generation(
                prompt=params.prompt,
                negative_prompt=params.negative_prompt,
                model_id=labels.model_id,
                model_name=labels.model_name,
                lora_id=labels.lora_id,
                lora_name=labels.lora_name,
                lora_strength=params.lora.strength if params.lora else None,
                seed=params.seed,
                width=params.width,
                height=params.height,
                steps=params.steps,
                guidance_scale=params.guidance_scale,
                num_images=params.num_images,
                duration_ms=duration_ms,
                device=output.device,
                model_config_json=output.model_config,
                comparison_id=cell.comparison_id if cell else None,
                comparison_index=cell.index if cell else None,
            )
            db.add(generation)
            db.flush()  # assigns generation.id for the filenames
            for index, (image, seed) in enumerate(zip(output.images, output.seeds, strict=True)):
                relative = f"{day_folder}/{generation.id:06d}_{index}_{seed}.png"
                path = resolve_within(output_dir, relative)
                path.parent.mkdir(parents=True, exist_ok=True)
                image.save(path, format="PNG")
                written.append(path)
                generation.images.append(
                    GenerationImage(
                        index=index,
                        seed=seed,
                        file_path=relative,
                        width=image.width,
                        height=image.height,
                        file_size_bytes=path.stat().st_size,
                        safety_blocked=output.is_blocked(index),
                    )
                )
            db.commit()
            return generation.id
        except Exception:
            # Don't leave orphaned image files behind for a generation that isn't in history.
            db.rollback()
            for path in written:
                path.unlink(missing_ok=True)
            raise
