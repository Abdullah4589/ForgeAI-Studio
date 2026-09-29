"""In-process background job queue.

A single worker thread runs jobs one at a time: GPU work can't usefully run in parallel, and
serial execution keeps memory predictable. The public surface (submit/get/cancel) is small so it
can later be backed by Redis/Celery without touching routes.
"""

import logging
import queue
import threading
import time
import uuid
from collections import OrderedDict
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from ai.errors import AIError, GenerationCancelledError

logger = logging.getLogger(__name__)

MAX_RETAINED_JOBS = 200


class JobStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

    @property
    def is_terminal(self) -> bool:
        return self in (JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED)


@dataclass
class JobSnapshot:
    id: str
    kind: str
    status: JobStatus
    step: int
    total_steps: int
    message: str
    created_at: float
    started_at: float | None
    finished_at: float | None
    result: dict[str, Any] | None
    error: dict[str, str] | None
    version: int


@dataclass
class Job:
    id: str
    kind: str
    run: "Callable[[JobContext], dict[str, Any]]"
    status: JobStatus = JobStatus.QUEUED
    step: int = 0
    total_steps: int = 0
    message: str = "Queued"
    created_at: float = field(default_factory=time.time)
    started_at: float | None = None
    finished_at: float | None = None
    result: dict[str, Any] | None = None
    error: dict[str, str] | None = None
    # Incremented on every change so pollers (SSE) can cheaply detect updates.
    version: int = 0
    cancel_event: threading.Event = field(default_factory=threading.Event)


class JobContext:
    """What a running job may touch: progress reporting and its cancellation flag."""

    def __init__(self, manager: "JobManager", job: Job) -> None:
        self._manager = manager
        self._job = job

    @property
    def cancel_event(self) -> threading.Event:
        return self._job.cancel_event

    def report_progress(self, step: int, total_steps: int, message: str) -> None:
        self._manager._update(self._job, step=step, total_steps=total_steps, message=message)


class JobManager:
    def __init__(
        self,
        idle_seconds: float = 0,
        on_idle: Callable[[], None] | None = None,
    ) -> None:
        self._jobs: OrderedDict[str, Job] = OrderedDict()
        self._queue: queue.Queue[Job | None] = queue.Queue()
        self._lock = threading.Lock()
        self._idle_seconds = idle_seconds
        self._on_idle = on_idle
        self._worker = threading.Thread(target=self._work, name="forge-job-worker", daemon=True)
        self._started = False

    def start(self) -> None:
        if not self._started:
            self._worker.start()
            self._started = True

    def shutdown(self, timeout: float = 5.0) -> None:
        with self._lock:
            for job in self._jobs.values():
                if not job.status.is_terminal:
                    job.cancel_event.set()
        self._queue.put(None)
        if self._started:
            self._worker.join(timeout)

    def submit(self, kind: str, run: Callable[[JobContext], dict[str, Any]]) -> JobSnapshot:
        job = Job(id=uuid.uuid4().hex, kind=kind, run=run)
        with self._lock:
            self._jobs[job.id] = job
            self._evict_old_jobs()
            snapshot = self._snapshot(job)
        self._queue.put(job)
        return snapshot

    def get(self, job_id: str) -> JobSnapshot | None:
        with self._lock:
            job = self._jobs.get(job_id)
            return self._snapshot(job) if job else None

    def active_job(self, kind: str) -> JobSnapshot | None:
        with self._lock:
            for job in self._jobs.values():
                if job.kind == kind and not job.status.is_terminal:
                    return self._snapshot(job)
        return None

    def cancel(self, job_id: str) -> JobSnapshot | None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return None
            if job.status == JobStatus.QUEUED:
                self._finish_locked(job, JobStatus.CANCELLED, message="Cancelled")
            elif job.status == JobStatus.RUNNING:
                job.cancel_event.set()
                job.message = "Cancelling…"
                job.version += 1
            return self._snapshot(job)

    # ---- worker -------------------------------------------------------------------------

    def _work(self) -> None:
        while True:
            try:
                timeout = self._idle_seconds if self._idle_seconds > 0 else None
                job = self._queue.get(timeout=timeout)
            except queue.Empty:
                self._run_idle_hook()
                continue
            if job is None:
                return
            self._execute(job)

    def _run_idle_hook(self) -> None:
        if self._on_idle is None:
            return
        try:
            self._on_idle()
        except Exception:
            logger.exception("idle_hook_failed")

    def _execute(self, job: Job) -> None:
        with self._lock:
            if job.status != JobStatus.QUEUED:  # cancelled while waiting
                return
            job.status = JobStatus.RUNNING
            job.started_at = time.time()
            job.message = "Starting"
            job.version += 1
        try:
            result = job.run(JobContext(self, job))
        except GenerationCancelledError:
            self._finish(job, JobStatus.CANCELLED, message="Cancelled")
        except AIError as exc:
            logger.warning("job_failed", extra={"job_id": job.id, "code": exc.code})
            self._finish(job, JobStatus.FAILED, error={"code": exc.code, "message": exc.message})
        except Exception:
            logger.exception("job_crashed", extra={"job_id": job.id})
            self._finish(
                job,
                JobStatus.FAILED,
                error={"code": "internal_error", "message": "The job failed unexpectedly."},
            )
        else:
            self._finish(job, JobStatus.COMPLETED, result=result, message="Completed")

    def _update(self, job: Job, **changes: Any) -> None:
        with self._lock:
            for key, value in changes.items():
                setattr(job, key, value)
            job.version += 1

    def _finish(self, job: Job, status: JobStatus, **changes: Any) -> None:
        with self._lock:
            self._finish_locked(job, status, **changes)

    def _finish_locked(self, job: Job, status: JobStatus, **changes: Any) -> None:
        for key, value in changes.items():
            setattr(job, key, value)
        if status == JobStatus.FAILED and "message" not in changes:
            job.message = "Failed"
        job.status = status
        job.finished_at = time.time()
        job.version += 1

    def _evict_old_jobs(self) -> None:
        while len(self._jobs) > MAX_RETAINED_JOBS:
            oldest_id = next(iter(self._jobs))
            if not self._jobs[oldest_id].status.is_terminal:
                break
            self._jobs.pop(oldest_id)

    @staticmethod
    def _snapshot(job: Job) -> JobSnapshot:
        return JobSnapshot(
            id=job.id,
            kind=job.kind,
            status=job.status,
            step=job.step,
            total_steps=job.total_steps,
            message=job.message,
            created_at=job.created_at,
            started_at=job.started_at,
            finished_at=job.finished_at,
            result=job.result,
            error=job.error,
            version=job.version,
        )
