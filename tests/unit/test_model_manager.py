import threading
import time
from pathlib import Path

from ai.model_manager.manager import ModelManager
from ai.pipelines.factory import PipelineRequest


def request(name: str) -> PipelineRequest:
    return PipelineRequest(
        path=Path(name),
        source_type="diffusers",
        architecture="sd15",
        device="cpu",
        enable_cpu_offload=False,
    )


class RecordingBuilder:
    def __init__(self) -> None:
        self.built: list[str] = []

    def __call__(self, req: PipelineRequest) -> object:
        self.built.append(str(req.path))
        return object()


def test_same_model_is_reused() -> None:
    builder = RecordingBuilder()
    manager = ModelManager(builder)
    first = manager.load(request("a"))
    assert manager.load(request("a")) is first
    assert builder.built == ["a"]


def test_switching_models_replaces_the_loaded_one() -> None:
    builder = RecordingBuilder()
    manager = ModelManager(builder)
    manager.load(request("a"))
    manager.load(request("b"))
    assert builder.built == ["a", "b"]
    loaded = manager.loaded_request()
    assert loaded is not None and loaded.path == Path("b")


def test_unload() -> None:
    manager = ModelManager(RecordingBuilder())
    assert manager.unload() is False
    manager.load(request("a"))
    assert manager.unload() is True
    assert manager.loaded_request() is None


def test_loaded_request_does_not_wait_for_a_running_generation() -> None:
    manager = ModelManager(RecordingBuilder())
    manager.load(request("a"))
    holding = threading.Event()
    release = threading.Event()

    def generate() -> None:
        with manager.lock:  # a generation holds this for its whole run
            holding.set()
            release.wait(5)

    worker = threading.Thread(target=generate)
    worker.start()
    assert holding.wait(5)
    started = time.monotonic()
    loaded = manager.loaded_request()
    assert time.monotonic() - started < 0.5
    assert loaded is not None and loaded.path == Path("a")
    release.set()
    worker.join()
