import threading
import time
from collections.abc import Iterator
from typing import Any

import pytest

from ai.errors import GenerationCancelledError, OutOfMemoryError
from forge_api.jobs.manager import JobContext, JobManager, JobSnapshot, JobStatus


@pytest.fixture
def manager() -> Iterator[JobManager]:
    jobs = JobManager()
    jobs.start()
    yield jobs
    jobs.shutdown()


def wait_for_terminal(manager: JobManager, job_id: str, timeout: float = 5.0) -> JobSnapshot:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        job = manager.get(job_id)
        assert job is not None
        if job.status.is_terminal:
            return job
        time.sleep(0.01)
    raise AssertionError("job did not finish in time")


def test_completed_job_reports_result_and_progress(manager: JobManager) -> None:
    def run(ctx: JobContext) -> dict[str, Any]:
        ctx.report_progress(3, 3, "done")
        return {"value": 42}

    job = wait_for_terminal(manager, manager.submit("test", run).id)
    assert job.status == JobStatus.COMPLETED
    assert job.result == {"value": 42}
    assert (job.step, job.total_steps) == (3, 3)
    assert job.started_at is not None and job.finished_at is not None


def test_ai_error_becomes_failed_with_user_message(manager: JobManager) -> None:
    def run(_: JobContext) -> dict[str, Any]:
        raise OutOfMemoryError()

    job = wait_for_terminal(manager, manager.submit("test", run).id)
    assert job.status == JobStatus.FAILED
    assert job.error is not None
    assert job.error["code"] == "out_of_memory"
    assert "smaller resolution" in job.error["message"]


def test_unexpected_exception_hides_details(manager: JobManager) -> None:
    def run(_: JobContext) -> dict[str, Any]:
        raise ValueError("secret internal detail")

    job = wait_for_terminal(manager, manager.submit("test", run).id)
    assert job.status == JobStatus.FAILED
    assert job.error == {"code": "internal_error", "message": "The job failed unexpectedly."}


def test_cancel_running_job(manager: JobManager) -> None:
    started = threading.Event()

    def run(ctx: JobContext) -> dict[str, Any]:
        started.set()
        assert ctx.cancel_event.wait(5)
        raise GenerationCancelledError()

    job_id = manager.submit("test", run).id
    assert started.wait(5)
    assert manager.active_job("test") is not None
    manager.cancel(job_id)
    assert wait_for_terminal(manager, job_id).status == JobStatus.CANCELLED
    assert manager.active_job("test") is None


def test_progress_after_cancel_keeps_cancelling_message(manager: JobManager) -> None:
    started = threading.Event()
    progressed = threading.Event()

    def run(ctx: JobContext) -> dict[str, Any]:
        started.set()
        assert ctx.cancel_event.wait(5)
        ctx.report_progress(3, 10, "Step 3 of 10")
        progressed.set()
        time.sleep(0.2)  # give the test time to observe the in-flight state
        raise GenerationCancelledError()

    job_id = manager.submit("test", run).id
    assert started.wait(5)
    manager.cancel(job_id)
    assert progressed.wait(5)
    snapshot = manager.get(job_id)
    assert snapshot is not None
    assert (snapshot.step, snapshot.message) == (3, "Cancelling…")
    assert wait_for_terminal(manager, job_id).status == JobStatus.CANCELLED


def test_cancel_queued_job_never_runs(manager: JobManager) -> None:
    release = threading.Event()
    ran: list[str] = []

    def blocker(_: JobContext) -> dict[str, Any]:
        release.wait(5)
        return {}

    def second(_: JobContext) -> dict[str, Any]:
        ran.append("second")
        return {}

    first_id = manager.submit("test", blocker).id
    second_id = manager.submit("test", second).id
    cancelled = manager.cancel(second_id)
    assert cancelled is not None and cancelled.status == JobStatus.CANCELLED
    release.set()
    wait_for_terminal(manager, first_id)
    time.sleep(0.05)
    assert ran == []


def test_cancel_unknown_job_returns_none(manager: JobManager) -> None:
    assert manager.cancel("missing") is None


def test_idle_hook_runs_when_queue_is_quiet() -> None:
    called = threading.Event()
    jobs = JobManager(idle_seconds=0.05, on_idle=called.set)
    jobs.start()
    try:
        assert called.wait(2)
    finally:
        jobs.shutdown()
