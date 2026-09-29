import asyncio
import json
from collections.abc import AsyncIterator

from fastapi import APIRouter, Request, status
from fastapi.responses import StreamingResponse

from forge_api.dependencies import DbDep, ServicesDep
from forge_api.errors import NotFoundError
from forge_api.jobs.manager import JobSnapshot
from forge_api.schemas.generation import CancelRequest, GenerateRequest, JobOut
from forge_api.services import generation_service

router = APIRouter(prefix="/api", tags=["generation"])

_POLL_SECONDS = 0.2
_HEARTBEAT_SECONDS = 15.0


def _job_out(job: JobSnapshot) -> JobOut:
    return JobOut.model_validate(job, from_attributes=True)


@router.post("/generate", response_model=JobOut, status_code=status.HTTP_202_ACCEPTED)
def generate(body: GenerateRequest, db: DbDep, services: ServicesDep) -> JobOut:
    return _job_out(generation_service.start_generation(db, services, body))


@router.post("/generate/cancel", response_model=JobOut)
def cancel(body: CancelRequest, services: ServicesDep) -> JobOut:
    job = generation_service.cancel_generation(services, body.job_id)
    if job is None:
        raise NotFoundError("Job not found.")
    return _job_out(job)


@router.get("/jobs/{job_id}", response_model=JobOut)
def get_job(job_id: str, services: ServicesDep) -> JobOut:
    job = services.jobs.get(job_id)
    if job is None:
        raise NotFoundError("Job not found.")
    return _job_out(job)


@router.get("/jobs/{job_id}/events")
async def job_events(job_id: str, request: Request, services: ServicesDep) -> StreamingResponse:
    """Server-Sent Events stream of job snapshots until the job reaches a terminal state."""
    if services.jobs.get(job_id) is None:
        raise NotFoundError("Job not found.")

    async def stream() -> AsyncIterator[str]:
        last_version = -1
        idle = 0.0
        while not await request.is_disconnected():
            job = services.jobs.get(job_id)
            if job is None:
                return
            if job.version != last_version:
                last_version = job.version
                idle = 0.0
                yield f"data: {json.dumps(_job_out(job).model_dump())}\n\n"
                if job.status.is_terminal:
                    return
            elif idle >= _HEARTBEAT_SECONDS:
                idle = 0.0
                yield ": keep-alive\n\n"  # stops proxies from closing an idle stream
            await asyncio.sleep(_POLL_SECONDS)
            idle += _POLL_SECONDS

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
