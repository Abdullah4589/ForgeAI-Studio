"""Comparison mode: one prompt generated once per value of a single varying setting."""

import logging
from dataclasses import dataclass
from functools import partial
from pathlib import Path
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.orm import Session, selectinload

from ai.errors import AIError, GenerationCancelledError
from forge_api.container import AppServices
from forge_api.db.models import Comparison, Generation
from forge_api.errors import NotFoundError
from forge_api.jobs.manager import JobContext, JobSnapshot
from forge_api.logging_config import truncate
from forge_api.schemas.compare import CompareRequest
from forge_api.schemas.generation import GenerateRequest
from forge_api.services import generation_service, history_service, model_service
from forge_api.services.generation_service import ComparisonCell, PreparedGeneration

logger = logging.getLogger(__name__)

JOB_KIND = "comparison"


@dataclass(frozen=True)
class PlannedComparison:
    prompt: str
    axis: str
    axis_values: list[Any]
    cells: list[PreparedGeneration]


def cell_requests(request: CompareRequest, seed: int) -> list[GenerateRequest]:
    """Expand a comparison into one single-image generation request per axis value."""
    shared: dict[str, Any] = {
        "prompt": request.prompt,
        "negative_prompt": request.negative_prompt,
        "lora_id": request.lora_id,
        "lora_strength": request.lora_strength,
        "width": request.width,
        "height": request.height,
        "steps": request.steps,
        "guidance_scale": request.guidance_scale,
        "seed": seed,
        "num_images": 1,
        "model_id": request.model_id,
    }
    cells: list[GenerateRequest] = []
    for value in request.axis.values:
        cell = dict(shared)
        if request.axis.kind == "lora_strength":
            # A null strength is the "without LoRA" baseline.
            cell.update(
                lora_id=None if value is None else request.lora_id, lora_strength=value or 0
            )
        elif request.axis.kind == "seed":
            cell["seed"] = value
        else:
            cell["model_id"] = value
        cells.append(GenerateRequest.model_validate(cell))
    return cells


def plan(db: Session, services: AppServices, request: CompareRequest) -> PlannedComparison:
    """Validate every cell before anything runs, so a bad value fails fast instead of midway."""
    seed = generation_service.resolve_seed(request.seed)
    prepared = []
    for cell in cell_requests(request, seed):
        model = model_service.get_model(db, cell.model_id)
        # cell_requests always sets a seed (shared or the axis value); 0 is a valid seed.
        cell_seed = cell.seed if cell.seed is not None else seed
        prepared.append(
            generation_service.prepare(db, services, model=model, request=cell, seed=cell_seed)
        )
    return PlannedComparison(
        prompt=request.prompt,
        axis=request.axis.kind,
        axis_values=list(request.axis.values),
        cells=prepared,
    )


def start_comparison(db: Session, services: AppServices, request: CompareRequest) -> JobSnapshot:
    planned = plan(db, services, request)
    generation_service.ensure_idle(services)
    comparison = Comparison(
        prompt=planned.prompt, axis=planned.axis, axis_values=planned.axis_values
    )
    db.add(comparison)
    db.commit()
    job = services.jobs.submit(JOB_KIND, partial(_run, services, comparison.id, planned))
    logger.info(
        "comparison_requested",
        extra={
            "job_id": job.id,
            "comparison_id": comparison.id,
            "axis": planned.axis,
            "cells": len(planned.cells),
            "prompt": truncate(planned.prompt),
        },
    )
    return job


def _run(
    services: AppServices, comparison_id: int, planned: PlannedComparison, ctx: JobContext
) -> dict[str, Any]:
    total_cells = len(planned.cells)
    total_steps = sum(cell.params.steps for cell in planned.cells)
    done_steps = 0
    try:
        for index, cell in enumerate(planned.cells):
            label = f"Cell {index + 1} of {total_cells}"
            offset = done_steps
            ctx.report_progress(offset, total_steps, f"{label} - preparing")

            def on_progress(
                step: int, total: int, offset: int = offset, label: str = label
            ) -> None:
                ctx.report_progress(offset + step, total_steps, f"{label} - step {step} of {total}")

            generation_service.execute(
                services,
                cell,
                on_progress,
                ctx.cancel_event,
                ComparisonCell(comparison_id=comparison_id, index=index),
            )
            done_steps += cell.params.steps
    except GenerationCancelledError:
        _finish(services, comparison_id, "cancelled")
        raise
    except AIError as exc:
        _finish(services, comparison_id, "failed", exc.message)
        raise
    except Exception:
        _finish(services, comparison_id, "failed", "The comparison failed unexpectedly.")
        raise
    _finish(services, comparison_id, "completed")
    logger.info("comparison_completed", extra={"comparison_id": comparison_id})
    return {"comparison_id": comparison_id}


def _finish(
    services: AppServices, comparison_id: int, status: str, error: str | None = None
) -> None:
    with services.session_factory() as db:
        comparison = db.get(Comparison, comparison_id)
        if comparison is not None:
            comparison.status = status
            comparison.error_message = error
            db.commit()


def mark_interrupted(db: Session) -> None:
    """Comparisons still 'running' at startup were cut off by a restart."""
    db.execute(
        update(Comparison).where(Comparison.status == "running").values(status="interrupted")
    )
    db.commit()


def list_comparisons(db: Session, limit: int) -> list[Comparison]:
    return list(db.scalars(select(Comparison).order_by(Comparison.id.desc()).limit(limit)))


def get_comparison(db: Session, comparison_id: int) -> Comparison:
    comparison = db.scalar(
        select(Comparison)
        .where(Comparison.id == comparison_id)
        .options(selectinload(Comparison.generations).selectinload(Generation.images))
    )
    if comparison is None:
        raise NotFoundError("Comparison not found.")
    return comparison


def delete_comparison(db: Session, output_dir: Path, comparison_id: int) -> None:
    """Delete a comparison together with its cells' generations and image files."""
    comparison = get_comparison(db, comparison_id)
    for generation_id in [g.id for g in comparison.generations]:
        history_service.delete_generation(db, output_dir, generation_id)
    db.delete(comparison)
    db.commit()
    logger.info("comparison_deleted", extra={"comparison_id": comparison_id})
