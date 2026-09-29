"""Backend behaviour tests.

The Diffusers backend is exercised with a fake pipeline and a minimal fake `torch` module, so
these run in CI without installing PyTorch or downloading weights.
"""

import sys
import threading
import types
from pathlib import Path
from typing import Any

import pytest

from ai.errors import GenerationCancelledError, GenerationFailedError, OutOfMemoryError
from ai.generation.diffusers_backend import DiffusersBackend
from ai.generation.mock_backend import MockBackend
from ai.generation.types import GenerationParams, LoraRef, ModelRef
from ai.model_manager.manager import ModelManager
from ai.pipelines.factory import PipelineRequest


def params(**overrides: Any) -> GenerationParams:
    values: dict[str, Any] = {
        "model": ModelRef(path=Path("m"), source_type="diffusers", architecture="sd15"),
        "prompt": "a lighthouse",
        "negative_prompt": "",
        "width": 64,
        "height": 64,
        "steps": 3,
        "guidance_scale": 7.0,
        "seed": 10,
        "num_images": 2,
    }
    values.update(overrides)
    return GenerationParams(**values)


# ---- mock backend ----------------------------------------------------------------------


def test_mock_backend_is_deterministic_and_reports_progress() -> None:
    progress: list[tuple[int, int]] = []
    backend = MockBackend()
    first = backend.generate(params(), lambda s, t: progress.append((s, t)), threading.Event())
    second = backend.generate(params(), lambda s, t: None, threading.Event())

    assert progress == [(1, 3), (2, 3), (3, 3)]
    assert first.seeds == [10, 11]
    assert first.images[0].size == (64, 64)
    assert first.images[0].tobytes() == second.images[0].tobytes()
    assert first.images[0].tobytes() != first.images[1].tobytes()


def test_mock_backend_honours_cancellation() -> None:
    cancel = threading.Event()
    cancel.set()
    with pytest.raises(GenerationCancelledError):
        MockBackend().generate(params(), lambda s, t: None, cancel)


def test_image_seed_wraps_at_32_bits() -> None:
    assert params(seed=2**32 - 1).image_seed(1) == 0


# ---- diffusers backend with fakes -------------------------------------------------------


class FakeOOM(Exception):
    pass


@pytest.fixture
def fake_torch(monkeypatch: pytest.MonkeyPatch) -> types.SimpleNamespace:
    class Generator:
        def __init__(self, device: str) -> None:
            self.device = device
            self.seed: int | None = None

        def manual_seed(self, seed: int) -> "Generator":
            self.seed = seed
            return self

    torch = types.SimpleNamespace(
        Generator=Generator,
        cuda=types.SimpleNamespace(OutOfMemoryError=FakeOOM, is_available=lambda: False),
    )
    monkeypatch.setitem(sys.modules, "torch", torch)
    return torch


class FakePipe:
    def __init__(self, error: Exception | None = None, unload_ok: bool = True) -> None:
        self.error = error
        self.unload_ok = unload_ok
        self.calls: list[dict[str, Any]] = []
        self.lora_calls: list[str] = []
        self.scheduler = types.SimpleNamespace()
        self.unet = types.SimpleNamespace(dtype="torch.float32")
        self._interrupt = False

    def __call__(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        for step in range(kwargs["num_inference_steps"]):
            kwargs["callback_on_step_end"](self, step, None, {})
            if self._interrupt:
                break
        return types.SimpleNamespace(images=["img"] * kwargs["num_images_per_prompt"])

    def load_lora_weights(self, *_: Any, **__: Any) -> None:
        self.lora_calls.append("load")

    def set_adapters(self, *_: Any, **__: Any) -> None:
        self.lora_calls.append("set")

    def unload_lora_weights(self) -> None:
        self.lora_calls.append("unload")
        if not self.unload_ok:
            raise RuntimeError("stuck adapter")


def backend_for(pipe: FakePipe) -> tuple[DiffusersBackend, ModelManager]:
    manager = ModelManager(lambda _req: pipe)
    return DiffusersBackend(manager, device="cpu", enable_cpu_offload=False), manager


def test_diffusers_backend_passes_parameters_and_seeds(fake_torch: Any) -> None:
    pipe = FakePipe()
    backend, _ = backend_for(pipe)
    progress: list[int] = []

    output = backend.generate(params(), lambda s, t: progress.append(s), threading.Event())

    call = pipe.calls[0]
    assert call["prompt"] == "a lighthouse"
    assert call["negative_prompt"] is None  # empty string is not sent
    assert [g.seed for g in call["generator"]] == [10, 11]
    assert progress == [1, 2, 3]
    assert output.seeds == [10, 11]
    assert output.model_config["cpu_offload"] is False


def test_diffusers_backend_maps_oom_to_friendly_error(fake_torch: Any) -> None:
    backend, _ = backend_for(FakePipe(error=FakeOOM()))
    with pytest.raises(OutOfMemoryError, match="smaller resolution"):
        backend.generate(params(), lambda s, t: None, threading.Event())


def test_diffusers_backend_maps_runtime_oom_message(fake_torch: Any) -> None:
    backend, _ = backend_for(FakePipe(error=RuntimeError("CUDA out of memory. Tried...")))
    with pytest.raises(OutOfMemoryError):
        backend.generate(params(), lambda s, t: None, threading.Event())


def test_diffusers_backend_hides_other_runtime_errors(fake_torch: Any) -> None:
    backend, _ = backend_for(FakePipe(error=RuntimeError("shape mismatch at layer 3")))
    with pytest.raises(GenerationFailedError) as info:
        backend.generate(params(), lambda s, t: None, threading.Event())
    assert "shape mismatch" not in info.value.message


def test_diffusers_backend_cancels_between_steps(fake_torch: Any) -> None:
    pipe = FakePipe()
    backend, _ = backend_for(pipe)
    cancel = threading.Event()

    def on_progress(step: int, _total: int) -> None:
        if step == 1:
            cancel.set()

    with pytest.raises(GenerationCancelledError):
        backend.generate(params(steps=10), on_progress, cancel)
    assert pipe._interrupt is True


def test_diffusers_backend_applies_and_removes_lora(fake_torch: Any) -> None:
    pipe = FakePipe()
    backend, manager = backend_for(pipe)
    lora = LoraRef(path=Path("loras/x.safetensors"), strength=0.7)
    backend.generate(params(lora=lora), lambda s, t: None, threading.Event())
    assert pipe.lora_calls == ["load", "set", "unload"]
    assert manager.loaded_request() is not None


def test_failed_lora_removal_unloads_model(fake_torch: Any) -> None:
    pipe = FakePipe(unload_ok=False)
    backend, manager = backend_for(pipe)
    lora = LoraRef(path=Path("loras/x.safetensors"), strength=1.0)
    backend.generate(params(lora=lora), lambda s, t: None, threading.Event())
    assert manager.loaded_request() is None


def test_preload_uses_backend_device_settings(fake_torch: Any) -> None:
    seen: list[PipelineRequest] = []
    manager = ModelManager(lambda req: seen.append(req) or FakePipe())
    DiffusersBackend(manager, device="cpu", enable_cpu_offload=True).preload(params().model)
    assert seen[0].device == "cpu"
    assert seen[0].enable_cpu_offload is False  # offload only applies on CUDA
