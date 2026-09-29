import json
import logging
from typing import Any

import pytest
from forge_api.logging_config import JsonFormatter, truncate
from forge_api.schemas.generation import GenerateRequest
from forge_api.schemas.settings import GenerationDefaults
from pydantic import ValidationError

from ai import device

VALID: dict[str, Any] = {"model_id": 1, "prompt": "a cat"}


def test_defaults_are_applied() -> None:
    request = GenerateRequest.model_validate(VALID)
    assert (request.width, request.height, request.steps, request.num_images) == (512, 512, 25, 1)
    assert request.seed is None


def test_prompt_is_stripped() -> None:
    assert GenerateRequest.model_validate({**VALID, "prompt": "  a cat  "}).prompt == "a cat"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("prompt", ""),
        ("prompt", "   "),
        ("prompt", "x" * 2001),
        ("width", 500),  # not a multiple of 8
        ("width", 128),
        ("height", 2048),
        ("steps", 0),
        ("steps", 151),
        ("guidance_scale", -1),
        ("guidance_scale", 31),
        ("num_images", 0),
        ("num_images", 5),
        ("seed", -1),
        ("seed", 2**32),
        ("lora_strength", 2.5),
    ],
)
def test_invalid_values_are_rejected(field: str, value: Any) -> None:
    with pytest.raises(ValidationError) as info:
        GenerateRequest.model_validate({**VALID, field: value})
    assert info.value.errors()[0]["loc"] == (field,)


def test_unknown_fields_are_rejected() -> None:
    with pytest.raises(ValidationError):
        GenerateRequest.model_validate({**VALID, "sampler": "euler"})


def test_generation_defaults_share_limits() -> None:
    with pytest.raises(ValidationError):
        GenerationDefaults(width=513)


def test_resolve_device_falls_back_to_cpu(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(device, "cuda_available", lambda: False)
    assert device.resolve_device("auto") == "cpu"
    assert device.resolve_device("cuda") == "cpu"
    monkeypatch.setattr(device, "cuda_available", lambda: True)
    assert device.resolve_device("auto") == "cuda"
    assert device.resolve_device("cpu") == "cpu"


def test_gpu_info_without_torch(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(device, "load_torch", lambda: None)
    info = device.gpu_info()
    assert info.torch_installed is False
    assert info.cuda_available is False


def test_json_formatter_includes_extra_fields() -> None:
    record = logging.makeLogRecord({"msg": "model_loaded", "levelname": "INFO", "seconds": 1.5})
    payload = json.loads(JsonFormatter().format(record))
    assert payload["event"] == "model_loaded"
    assert payload["seconds"] == 1.5


def test_truncate() -> None:
    assert truncate("short") == "short"
    assert truncate("x" * 100, limit=10) == "x" * 10 + "…"
