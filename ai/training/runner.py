"""Starts the training worker process and follows it (runs in the app's job thread)."""

import logging
import os
import subprocess
import sys
import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from ai.training import protocol
from ai.training.config import TrainingConfig

logger = logging.getLogger(__name__)

# The repository root, which must be importable for `python -m ai.training.worker`.
_IMPORT_ROOT = Path(__file__).resolve().parents[2]
# How long a cancelled worker gets to stop between steps before it is killed. One CPU training
# step at 512 px took ~13 s; this leaves room for a slow step or a checkpoint save.
CANCEL_GRACE_SECONDS = 90.0


@dataclass
class TrainingOutcome:
    status: Literal["completed", "cancelled", "failed"]
    lora_path: str | None = None
    error: dict[str, str] | None = None
    last_checkpoint: str | None = None
    avg_step_seconds: float | None = None
    samples: list[dict[str, Any]] = field(default_factory=list)
    log_path: str = ""


def run_worker(
    config: TrainingConfig,
    work_dir: Path,
    on_event: Callable[[dict[str, Any]], None],
    cancel: threading.Event,
    *,
    grace_seconds: float = CANCEL_GRACE_SECONDS,
    python: str = sys.executable,
) -> TrainingOutcome:
    work_dir.mkdir(parents=True, exist_ok=True)
    config_path = work_dir / "config.json"
    cancel_path = work_dir / "cancel"
    log_path = work_dir / "worker.log"
    cancel_path.unlink(missing_ok=True)
    config.write(config_path)

    env = {
        **os.environ,
        "PYTHONPATH": os.pathsep.join(
            filter(None, [str(_IMPORT_ROOT), os.environ.get("PYTHONPATH")])
        ),
        "PYTHONUNBUFFERED": "1",
        "PYTHONIOENCODING": "utf-8",
    }
    outcome = TrainingOutcome(status="failed", log_path=str(log_path))
    with log_path.open("w", encoding="utf-8") as log:
        process = subprocess.Popen(
            [python, "-m", "ai.training.worker", str(config_path), str(cancel_path)],
            cwd=_IMPORT_ROOT,
            env=env,
            stdout=subprocess.PIPE,
            stderr=log,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        logger.info(
            "training_worker_started", extra={"pid": process.pid, "work_dir": str(work_dir)}
        )
        finished = threading.Event()
        killed = threading.Event()
        watcher = threading.Thread(
            target=_watch_cancel,
            args=(process, cancel, cancel_path, finished, killed, grace_seconds),
            daemon=True,
        )
        watcher.start()
        try:
            assert process.stdout is not None
            for line in process.stdout:
                event = protocol.parse(line)
                if event is None:
                    log.write(line)  # library chatter on stdout
                    continue
                _record(outcome, event)
                on_event(event)
            returncode = process.wait()
        finally:
            finished.set()
            if process.poll() is None:
                process.kill()
                process.wait()

    if returncode == protocol.EXIT_OK and outcome.lora_path:
        outcome.status = "completed"
    elif returncode == protocol.EXIT_CANCELLED or cancel.is_set():
        outcome.status = "cancelled"
    else:
        outcome.status = "failed"
        if outcome.error is None:
            reason = "was stopped" if killed.is_set() else f"exited with code {returncode}"
            outcome.error = {
                "code": "training_crashed",
                "message": f"The training process {reason} unexpectedly. "
                "The training log has the details.",
            }
    logger.info(
        "training_worker_finished",
        extra={"status": outcome.status, "returncode": returncode, "killed": killed.is_set()},
    )
    return outcome


def _record(outcome: TrainingOutcome, event: dict[str, Any]) -> None:
    kind = event.get("type")
    if kind == "checkpoint":
        outcome.last_checkpoint = event.get("path")
    elif kind == "saved":
        outcome.avg_step_seconds = event.get("avg_step_seconds")
    elif kind == "sample":
        outcome.samples.append(event)
    elif kind == "done":
        outcome.lora_path = event.get("lora_path")
    elif kind == "error":
        outcome.error = {"code": str(event.get("code")), "message": str(event.get("message"))}
    elif kind == "cancelled" and event.get("last_checkpoint"):
        outcome.last_checkpoint = event["last_checkpoint"]


def _watch_cancel(
    process: "subprocess.Popen[str]",
    cancel: threading.Event,
    cancel_path: Path,
    finished: threading.Event,
    killed: threading.Event,
    grace_seconds: float,
) -> None:
    while not finished.is_set():
        if cancel.wait(0.5):
            break
    if finished.is_set():
        return
    cancel_path.touch()  # ask the worker to stop at the next step
    if not finished.wait(grace_seconds) and process.poll() is None:
        logger.warning("training_worker_killed", extra={"pid": process.pid})
        killed.set()
        process.kill()
