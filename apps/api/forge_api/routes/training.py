from typing import Annotated

from fastapi import APIRouter, Query, status
from fastapi.responses import FileResponse

from forge_api.dependencies import DbDep, ServicesDep
from forge_api.schemas.generation import JobOut
from forge_api.schemas.training import TrainingJobOut, TrainingRequest, TrainingRunOut
from forge_api.services import training_service

router = APIRouter(prefix="/api/training", tags=["training"])


@router.post("", response_model=TrainingJobOut, status_code=status.HTTP_202_ACCEPTED)
def start_training(body: TrainingRequest, services: ServicesDep) -> TrainingJobOut:
    """Queue a LoRA training run. Progress and cancellation use the generic /api/jobs endpoints."""
    job, run = training_service.start_training(services, body)
    return TrainingJobOut(
        **JobOut.model_validate(job, from_attributes=True).model_dump(), run_id=run.id
    )


@router.get("", response_model=list[TrainingRunOut])
def list_runs(db: DbDep, limit: Annotated[int, Query(ge=1, le=100)] = 20) -> list[TrainingRunOut]:
    return [training_service.run_out(run) for run in training_service.list_runs(db, limit)]


@router.get("/{run_id}", response_model=TrainingRunOut)
def get_run(run_id: int, db: DbDep) -> TrainingRunOut:
    return training_service.run_out(training_service.get_run(db, run_id))


@router.delete("/{run_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_run(run_id: int, db: DbDep, services: ServicesDep) -> None:
    training_service.delete_run(db, services, run_id)


@router.get("/{run_id}/samples/{index}")
def sample_image(run_id: int, index: int, db: DbDep, services: ServicesDep) -> FileResponse:
    run = training_service.get_run(db, run_id)
    return FileResponse(training_service.sample_path(services, run, index), media_type="image/png")
