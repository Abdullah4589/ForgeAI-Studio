from typing import Annotated

from fastapi import APIRouter, Query, status

from forge_api.db.models import Comparison
from forge_api.dependencies import DbDep, ServicesDep
from forge_api.jobs.manager import JobSnapshot
from forge_api.schemas.compare import CompareRequest, ComparisonOut, ComparisonSummary
from forge_api.schemas.generation import JobOut
from forge_api.schemas.history import GenerationOut
from forge_api.services import compare_service

router = APIRouter(prefix="/api", tags=["compare"])


def _job_out(job: JobSnapshot) -> JobOut:
    return JobOut.model_validate(job, from_attributes=True)


def _comparison_out(comparison: Comparison) -> ComparisonOut:
    summary = ComparisonSummary.model_validate(comparison)
    return ComparisonOut(
        **summary.model_dump(),
        cells=[GenerationOut.model_validate(g) for g in comparison.generations],
    )


@router.post("/compare", response_model=JobOut, status_code=status.HTTP_202_ACCEPTED)
def compare(body: CompareRequest, db: DbDep, services: ServicesDep) -> JobOut:
    """Queue a comparison. Progress and cancellation use the generic /api/jobs endpoints."""
    return _job_out(compare_service.start_comparison(db, services, body))


@router.get("/comparisons", response_model=list[ComparisonSummary])
def list_comparisons(
    db: DbDep, limit: Annotated[int, Query(ge=1, le=100)] = 20
) -> list[Comparison]:
    return compare_service.list_comparisons(db, limit)


@router.get("/comparisons/{comparison_id}", response_model=ComparisonOut)
def get_comparison(comparison_id: int, db: DbDep) -> ComparisonOut:
    return _comparison_out(compare_service.get_comparison(db, comparison_id))


@router.delete("/comparisons/{comparison_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_comparison(comparison_id: int, db: DbDep, services: ServicesDep) -> None:
    compare_service.delete_comparison(db, services.settings.output_directory, comparison_id)
