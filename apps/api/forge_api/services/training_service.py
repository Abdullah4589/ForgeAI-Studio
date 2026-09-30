"""LoRA training runs: validation, the background job, progress persistence and LoRA registration.

The heavy lifting happens in a separate worker process (ai.training.worker); this service only
prepares its config, relays progress to the job/DB, and registers the resulting LoRA.
"""

import logging
import math
import os
import shutil
import time
import uuid
from datetime import UTC, datetime
from functools import partial
from pathlib import Path
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from ai.errors import GenerationCancelledError
from ai.lora.inspect import inspect_lora
from ai.training.config import TrainingConfig, TrainingItem, training_caption
from ai.training.errors import TrainingFailedError
from ai.training.runner import TrainingOutcome, run_worker
from forge_api.container import AppServices
from forge_api.db.models import Lora, TrainingJob
from forge_api.errors import ConflictError, NotFoundError, UnprocessableError
from forge_api.jobs.manager import JobContext, JobSnapshot
from forge_api.schemas.training import TrainingRequest, TrainingRunOut, TrainingSample
from forge_api.services import dataset_service, generation_service, model_service
from forge_api.services.storage import resolve_within, safe_filename

logger = logging.getLogger(__name__)

JOB_KIND = "training"
LORA_SUFFIX = ".safetensors"
# Loss points kept per run; long runs are thinned evenly so charts stay light.
MAX_LOSS_POINTS = 500
# How often live progress is written to the database.
PERSIST_INTERVAL_SECONDS = 1.0


def run_dir(services: AppServices, run_id: int) -> Path:
    return resolve_within(services.settings.training_directory, str(run_id))


def start_training(
    services: AppServices, request: TrainingRequest
) -> tuple[JobSnapshot, TrainingJob]:
    settings = services.settings
    with services.session_factory() as db:
        dataset = dataset_service.get_dataset(db, request.dataset_id)
        if not dataset.images:
            raise UnprocessableError("The dataset has no images to train on.")
        model = model_service.get_model(db, request.base_model_id)
        model_service.require_usable(model)
        if model.architecture != "sd15":
            raise UnprocessableError("Only Stable Diffusion 1.x models can be trained for now.")
        filename = safe_filename(f"{request.name}{LORA_SUFFIX}", required_suffix=LORA_SUFFIX)
        name = filename.removesuffix(LORA_SUFFIX)
        exists = resolve_within(settings.lora_directory, filename).exists()
        if exists or db.scalar(select(Lora).where(Lora.filename == filename)):
            raise ConflictError(f"A LoRA named '{filename}' already exists. Choose another name.")
        generation_service.ensure_idle(services)

        trigger = request.trigger_word.strip()
        items = [
            TrainingItem(
                image_path=str(
                    dataset_service.image_path(settings, dataset.id, image.stored_filename)
                ),
                caption=training_caption(trigger, image.caption),
            )
            for image in dataset.images
        ]
        # Sample with the dataset's own captions so results are comparable to the training data.
        prompts = [item.caption for item in items if item.caption][: max(request.sample_count, 1)]
        run = TrainingJob(
            name=name,
            dataset_id=dataset.id,
            dataset_name=dataset.name,
            base_model_id=model.id,
            base_model_name=model.name,
            trigger_word=trigger,
            resolution=request.resolution,
            rank=request.rank,
            alpha=request.alpha,
            learning_rate=request.learning_rate,
            batch_size=request.batch_size,
            steps=request.steps,
            save_every=request.save_every,
            seed=generation_service.resolve_seed(request.seed),
            sample_count=request.sample_count,
            sample_steps=request.sample_steps,
            image_count=len(items),
        )
        db.add(run)
        db.commit()
        config = TrainingConfig(
            backend=settings.training_backend,
            model_path=str(model_service.model_path(services, model)),
            source_type="diffusers" if model.source_type == "diffusers" else "single_file",
            architecture=model.architecture,
            output_dir=str(run_dir(services, run.id) / "output"),
            name=name,
            items=items,
            resolution=run.resolution,
            rank=run.rank,
            alpha=run.alpha,
            learning_rate=run.learning_rate,
            batch_size=run.batch_size,
            steps=run.steps,
            save_every=run.save_every,
            seed=run.seed,
            device=services.device,
            sample_prompts=prompts or [trigger or "a picture"],
            sample_count=run.sample_count,
            sample_steps=run.sample_steps,
            mock_step_delay_seconds=settings.mock_training_step_delay_seconds,
        )
        job = services.jobs.submit(JOB_KIND, partial(_run, services, run.id, config))
        run.job_id = job.id
        db.commit()
        logger.info(
            "training_requested",
            extra={
                "run_id": run.id,
                "job_id": job.id,
                "dataset_id": dataset.id,
                "model": model.name,
                "images": len(items),
                "steps": run.steps,
                "resolution": run.resolution,
            },
        )
        return job, run


class _Progress:
    """Relays worker events to the job snapshot and (throttled) to the database."""

    def __init__(self, services: AppServices, run_id: int, ctx: JobContext, steps: int) -> None:
        self._services = services
        self._run_id = run_id
        self._ctx = ctx
        self._steps = steps
        self._step = 0
        self._loss: float | None = None
        self._history: list[list[float]] = []
        self._peak_memory = 0
        self._last_write = 0.0

    def __call__(self, event: dict[str, Any]) -> None:
        kind = event.get("type")
        if kind == "status":
            self._ctx.report_progress(self._step, self._steps, str(event.get("message")))
        elif kind == "progress":
            self._step = int(event["step"])
            self._loss = float(event["loss"])
            self._history.append([self._step, self._loss])
            self._peak_memory = max(self._peak_memory, int(event.get("memory_bytes") or 0))
            self._ctx.report_progress(
                self._step,
                self._steps,
                f"Step {self._step} of {self._steps}, loss {self._loss:.4f}",
            )
            self.persist(force=self._step == self._steps)
        elif kind == "checkpoint":
            self._write(last_checkpoint=self._relative(str(event["path"])))
        elif kind == "sample":
            self._ctx.report_progress(
                self._steps, self._steps, f"Generated sample {int(event['index']) + 1}"
            )

    def persist(self, *, force: bool = False) -> None:
        now = time.monotonic()
        if not force and now - self._last_write < PERSIST_INTERVAL_SECONDS:
            return
        self._last_write = now
        self._write(
            current_step=self._step,
            last_loss=self._loss,
            loss_history=thin(self._history),
            peak_memory_bytes=self._peak_memory or None,
        )

    def _write(self, **values: Any) -> None:
        with self._services.session_factory() as db:
            db.execute(update(TrainingJob).where(TrainingJob.id == self._run_id).values(**values))
            db.commit()

    def _relative(self, path: str) -> str:
        return (
            Path(path)
            .resolve()
            .relative_to(self._services.settings.training_directory.resolve())
            .as_posix()
        )


def thin(history: list[list[float]]) -> list[list[float]]:
    """At most MAX_LOSS_POINTS evenly spaced points, always keeping the latest."""
    if len(history) <= MAX_LOSS_POINTS:
        return list(history)
    stride = math.ceil(len(history) / MAX_LOSS_POINTS)
    thinned = history[::stride]
    return thinned if thinned[-1] == history[-1] else [*thinned, history[-1]]


def _run(
    services: AppServices, run_id: int, config: TrainingConfig, ctx: JobContext
) -> dict[str, Any]:
    # Training needs all the memory it can get: free the generation model and the captioner.
    services.backend.release()
    services.captioner.release()
    _update(services, run_id, status="running", started_at=datetime.now(UTC))
    ctx.report_progress(0, config.steps, "Starting training")
    progress = _Progress(services, run_id, ctx, config.steps)
    outcome = run_worker(config, run_dir(services, run_id), progress, ctx.cancel_event)
    progress.persist(force=True)

    if outcome.status == "completed":
        return _complete(services, run_id, config, outcome)
    common = {
        "finished_at": datetime.now(UTC),
        "last_checkpoint": _relative_or_none(services, outcome.last_checkpoint),
    }
    if outcome.status == "cancelled":
        _update(services, run_id, status="cancelled", **common)
        logger.info("training_cancelled", extra={"run_id": run_id})
        raise GenerationCancelledError("Training was cancelled.")
    message = (outcome.error or {}).get("message", "Training failed.")
    _update(services, run_id, status="failed", error_message=message, **common)
    logger.warning("training_failed", extra={"run_id": run_id, "log": outcome.log_path})
    raise TrainingFailedError(message)


def _complete(
    services: AppServices, run_id: int, config: TrainingConfig, outcome: TrainingOutcome
) -> dict[str, Any]:
    assert outcome.lora_path is not None
    lora_id = _register_lora(services, run_id, config, Path(outcome.lora_path))
    samples = [
        {
            "index": int(sample["index"]),
            "path": _relative_or_none(services, str(sample["path"])),
            "safety_blocked": bool(sample.get("safety_blocked")),
        }
        for sample in outcome.samples
    ]
    _update(
        services,
        run_id,
        status="completed",
        finished_at=datetime.now(UTC),
        lora_id=lora_id,
        samples=samples,
        avg_step_seconds=outcome.avg_step_seconds,
        last_checkpoint=_relative_or_none(services, outcome.last_checkpoint),
    )
    logger.info("training_completed", extra={"run_id": run_id, "lora_id": lora_id})
    return {"run_id": run_id, "lora_id": lora_id}


def _register_lora(
    services: AppServices, run_id: int, config: TrainingConfig, trained: Path
) -> int:
    """Copy the trained LoRA into the LoRA library so it's immediately usable."""
    settings = services.settings
    filename = f"{config.name}{LORA_SUFFIX}"
    destination = resolve_within(settings.lora_directory, filename)
    if destination.exists():
        raise TrainingFailedError(
            f"Training finished, but '{filename}' now exists in the LoRA folder. The trained file "
            f"was kept at {trained}."
        )
    settings.lora_directory.mkdir(parents=True, exist_ok=True)
    temp = resolve_within(settings.lora_directory, f".training-{uuid.uuid4().hex}.part")
    shutil.copy2(trained, temp)
    os.replace(temp, destination)
    info = inspect_lora(destination)
    with services.session_factory() as db:
        run = db.get(TrainingJob, run_id)
        assert run is not None
        lora = Lora(
            name=config.name,
            filename=filename,
            file_size_bytes=destination.stat().st_size,
            base_architecture=info.architecture,
            rank=info.rank,
            trigger_words=run.trigger_word,
            description=(
                f"Trained on '{run.dataset_name}' ({run.image_count} images, {run.steps} steps, "
                f"{run.resolution} px)."
            ),
        )
        db.add(lora)
        db.commit()
        logger.info("lora_imported", extra={"file": filename, "source": "training"})
        return lora.id


def _update(services: AppServices, run_id: int, **values: Any) -> None:
    with services.session_factory() as db:
        db.execute(update(TrainingJob).where(TrainingJob.id == run_id).values(**values))
        db.commit()


def _relative_or_none(services: AppServices, path: str | None) -> str | None:
    if not path:
        return None
    return (
        Path(path).resolve().relative_to(services.settings.training_directory.resolve()).as_posix()
    )


# ---- read / delete ----------------------------------------------------------------------


def mark_interrupted(db: Session) -> None:
    """Runs still queued or running at startup were cut off by a restart."""
    db.execute(
        update(TrainingJob)
        .where(TrainingJob.status.in_(["queued", "running"]))
        .values(
            status="interrupted",
            error_message="The app stopped while this run was in progress.",
        )
    )
    db.commit()


def list_runs(db: Session, limit: int) -> list[TrainingJob]:
    return list(db.scalars(select(TrainingJob).order_by(TrainingJob.id.desc()).limit(limit)))


def get_run(db: Session, run_id: int) -> TrainingJob:
    run = db.get(TrainingJob, run_id)
    if run is None:
        raise NotFoundError("Training run not found.")
    return run


def run_out(run: TrainingJob) -> TrainingRunOut:
    fields = {
        name: getattr(run, name) for name in TrainingRunOut.model_fields if hasattr(run, name)
    }
    fields["has_checkpoint"] = bool(run.last_checkpoint)
    fields["samples"] = [
        TrainingSample(index=s["index"], safety_blocked=s["safety_blocked"]) for s in run.samples
    ]
    return TrainingRunOut.model_validate(fields)


def delete_run(db: Session, services: AppServices, run_id: int) -> None:
    """Delete the run and its working files. A LoRA it produced stays in the library."""
    run = get_run(db, run_id)
    if run.status in ("queued", "running"):
        raise ConflictError("Cancel the run before deleting it.")
    folder = run_dir(services, run.id)
    db.delete(run)
    db.commit()
    if folder.exists():
        shutil.rmtree(folder)
    logger.info("training_run_deleted", extra={"run_id": run_id})


def sample_path(services: AppServices, run: TrainingJob, index: int) -> Path:
    sample = next((s for s in run.samples if s["index"] == index), None)
    if sample is None or not sample.get("path"):
        raise NotFoundError("Sample not found.")
    path = resolve_within(services.settings.training_directory, sample["path"])
    if not path.is_file():
        raise NotFoundError("Sample file is missing.")
    return path
