import threading
import time
from pathlib import Path
from typing import Any

import pytest

from ai.lora.inspect import inspect_lora
from ai.training import protocol
from ai.training.config import TrainingConfig, TrainingItem, training_caption
from ai.training.errors import TrainingCancelled, TrainingFailedError
from ai.training.mock_trainer import MOCK_FAIL_NAME, train
from ai.training.runner import run_worker
from forge_api.services.training_service import MAX_LOSS_POINTS, thin
from tests.helpers import encode, picture


def config(tmp_path: Path, **overrides: Any) -> TrainingConfig:
    image = tmp_path / "a.png"
    image.write_bytes(encode(picture(1, (64, 64))))
    values: dict[str, Any] = {
        "backend": "mock",
        "model_path": str(tmp_path / "model"),
        "source_type": "diffusers",
        "architecture": "sd15",
        "output_dir": str(tmp_path / "out"),
        "name": "my-lora",
        "items": [TrainingItem(str(image), "fgx, a red square")],
        "resolution": 256,
        "rank": 4,
        "alpha": 8.0,
        "learning_rate": 1e-4,
        "batch_size": 1,
        "steps": 6,
        "save_every": 2,
        "seed": 7,
        "device": "cpu",
        "sample_prompts": ["fgx, a red square"],
        "sample_count": 2,
        "sample_steps": 5,
    }
    values.update(overrides)
    return TrainingConfig(**values)


@pytest.mark.parametrize(
    ("trigger", "caption", "expected"),
    [
        ("fgx", "a red house", "fgx, a red house"),
        ("", "a red house", "a red house"),
        ("fgx", "", "fgx"),
        ("  fgx ", "  a red house ", "fgx, a red house"),
    ],
)
def test_training_caption(trigger: str, caption: str, expected: str) -> None:
    assert training_caption(trigger, caption) == expected


def test_protocol_round_trip(capsys: pytest.CaptureFixture[str]) -> None:
    protocol.emit("progress", step=3, loss=0.1)
    line = capsys.readouterr().out
    assert protocol.parse(line) == {"type": "progress", "step": 3, "loss": 0.1}
    assert protocol.parse("Loading weights: 50%") is None
    assert protocol.parse(protocol.MARKER + "{not json") is None
    assert protocol.parse(protocol.MARKER + '{"no_type": 1}') is None


def test_config_round_trip(tmp_path: Path) -> None:
    original = config(tmp_path)
    original.write(tmp_path / "config.json")
    assert TrainingConfig.read(tmp_path / "config.json") == original


def test_thin_keeps_latest_and_caps_size() -> None:
    history = [[float(step), 1.0 / step] for step in range(1, 1234)]
    thinned = thin(history)
    assert len(thinned) <= MAX_LOSS_POINTS + 1
    assert thinned[0] == history[0] and thinned[-1] == history[-1]
    assert thin(history[:10]) == history[:10]


# ---- mock trainer in-process ------------------------------------------------------------


def test_mock_trainer_emits_the_full_sequence(tmp_path: Path) -> None:
    events: list[dict[str, Any]] = []
    lora = train(
        config(tmp_path), lambda kind, **p: events.append({"type": kind, **p}), lambda: False
    )
    kinds = [e["type"] for e in events]
    assert kinds.count("progress") == 6
    assert [e["step"] for e in events if e["type"] == "checkpoint"] == [2, 4]  # not the last step
    assert kinds[-3:] == ["status", "sample", "sample"]
    assert inspect_lora(lora).architecture == "sd15"
    assert inspect_lora(lora).rank == 4


def test_mock_trainer_cancel_reports_last_checkpoint(tmp_path: Path) -> None:
    steps: list[int] = []

    def emit(kind: str, **payload: Any) -> None:
        if kind == "progress":
            steps.append(payload["step"])

    with pytest.raises(TrainingCancelled) as info:
        train(config(tmp_path, steps=50), emit, lambda: len(steps) >= 5)
    assert info.value.last_checkpoint is not None
    assert info.value.last_checkpoint.endswith("my-lora-step-000004.safetensors")


def test_mock_trainer_failure(tmp_path: Path) -> None:
    with pytest.raises(TrainingFailedError):
        train(config(tmp_path, name=MOCK_FAIL_NAME), lambda *a, **k: None, lambda: False)


# ---- real worker process (mock backend) --------------------------------------------------


def test_worker_process_completes(tmp_path: Path) -> None:
    events: list[dict[str, Any]] = []
    outcome = run_worker(config(tmp_path), tmp_path / "run", events.append, threading.Event())
    assert outcome.status == "completed"
    assert outcome.lora_path and Path(outcome.lora_path).is_file()
    assert outcome.last_checkpoint and outcome.last_checkpoint.endswith("step-000004.safetensors")
    assert len(outcome.samples) == 2
    assert outcome.avg_step_seconds is not None
    assert events[-1]["type"] == "done"
    assert (tmp_path / "run" / "worker.log").is_file()


def test_worker_process_cancels_gracefully(tmp_path: Path) -> None:
    cancel = threading.Event()
    progress: list[int] = []

    def on_event(event: dict[str, Any]) -> None:
        if event["type"] == "progress":
            progress.append(event["step"])
            if event["step"] == 3:
                cancel.set()

    slow = config(tmp_path, steps=500, mock_step_delay_seconds=0.02)
    outcome = run_worker(slow, tmp_path / "run", on_event, cancel)
    assert outcome.status == "cancelled"
    assert max(progress) < 500
    assert outcome.lora_path is None


def test_worker_that_ignores_cancel_is_killed(tmp_path: Path) -> None:
    cancel = threading.Event()
    stuck = config(tmp_path, steps=3, mock_step_delay_seconds=30)
    timer = threading.Timer(0.5, cancel.set)
    timer.start()
    started = time.monotonic()
    outcome = run_worker(stuck, tmp_path / "run", lambda e: None, cancel, grace_seconds=0.5)
    assert outcome.status == "cancelled"
    assert time.monotonic() - started < 20


def test_worker_failure_is_reported(tmp_path: Path) -> None:
    outcome = run_worker(
        config(tmp_path, name=MOCK_FAIL_NAME), tmp_path / "run", lambda e: None, threading.Event()
    )
    assert outcome.status == "failed"
    assert outcome.error == {
        "code": "training_failed",
        "message": "Mock training failed on purpose.",
    }


def test_worker_crash_is_reported(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # A config the worker can't parse makes it crash before sending any event.
    monkeypatch.setattr(TrainingConfig, "write", lambda self, path: path.write_text("{}"))
    outcome = run_worker(config(tmp_path), tmp_path / "run", lambda e: None, threading.Event())
    assert outcome.status == "failed"
    assert outcome.error is not None and outcome.error["code"] == "training_crashed"
    assert "Traceback" in (tmp_path / "run" / "worker.log").read_text(encoding="utf-8")
