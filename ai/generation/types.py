from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

from PIL.Image import Image

from ai.pipelines.factory import SourceType

# Seeds are stored as unsigned 32-bit ints so they round-trip through any generator backend.
MAX_SEED = 2**32 - 1

ProgressCallback = Callable[[int, int], None]
"""Called with (completed_steps, total_steps)."""


class CancelToken(Protocol):
    def is_set(self) -> bool: ...


@dataclass(frozen=True)
class ModelRef:
    path: Path
    source_type: SourceType
    architecture: str


@dataclass(frozen=True)
class LoraRef:
    path: Path
    strength: float


@dataclass(frozen=True)
class GenerationParams:
    model: ModelRef
    prompt: str
    negative_prompt: str
    width: int
    height: int
    steps: int
    guidance_scale: float
    seed: int
    num_images: int
    lora: LoraRef | None = None

    def image_seed(self, index: int) -> int:
        """Each image in a batch gets its own seed so any single image can be reproduced."""
        return (self.seed + index) % (MAX_SEED + 1)


@dataclass
class GenerationOutput:
    images: list[Image]
    seeds: list[int]
    device: str
    # Pipeline details worth persisting for reproducibility (dtype, scheduler, offload...).
    model_config: dict[str, Any] = field(default_factory=dict)
    # Per image: True when the model's safety checker replaced it with a black image.
    safety_blocked: list[bool] = field(default_factory=list)

    def is_blocked(self, index: int) -> bool:
        return index < len(self.safety_blocked) and self.safety_blocked[index]


class GenerationBackend(Protocol):
    def generate(
        self, params: GenerationParams, on_progress: ProgressCallback, cancel: CancelToken
    ) -> GenerationOutput: ...

    def preload(self, model: ModelRef) -> None:
        """Load the model ahead of time so the first generation starts faster."""
        ...

    def release(self) -> None:
        """Free any loaded model memory."""
        ...
