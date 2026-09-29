from typing import Literal

from ai.generation.diffusers_backend import DiffusersBackend
from ai.generation.mock_backend import MockBackend
from ai.generation.types import GenerationBackend
from ai.model_manager.manager import ModelManager


def create_backend(
    kind: Literal["diffusers", "mock"],
    *,
    model_manager: ModelManager,
    device: Literal["cuda", "cpu"],
    enable_cpu_offload: bool,
    mock_step_delay_seconds: float = 0.0,
) -> GenerationBackend:
    if kind == "mock":
        return MockBackend(step_delay_seconds=mock_step_delay_seconds)
    return DiffusersBackend(model_manager, device, enable_cpu_offload)
