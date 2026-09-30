"""Everything a training worker needs, passed to it as a JSON file."""

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal

TrainingBackend = Literal["diffusers", "mock"]


@dataclass(frozen=True)
class TrainingItem:
    image_path: str
    caption: str


@dataclass(frozen=True)
class TrainingConfig:
    backend: TrainingBackend
    model_path: str
    source_type: Literal["diffusers", "single_file"]
    architecture: str
    output_dir: str
    # File name (without extension) of the final LoRA.
    name: str
    items: list[TrainingItem]
    resolution: int
    rank: int
    alpha: float
    learning_rate: float
    batch_size: int
    steps: int
    # 0 disables intermediate checkpoints.
    save_every: int
    seed: int
    device: Literal["cuda", "cpu"]
    sample_prompts: list[str] = field(default_factory=list)
    sample_count: int = 2
    sample_steps: int = 20
    # Mock backend only: per-step delay so progress and cancel are observable in tests.
    mock_step_delay_seconds: float = 0.0

    def write(self, path: Path) -> None:
        path.write_text(json.dumps(asdict(self), indent=2), encoding="utf-8")

    @classmethod
    def read(cls, path: Path) -> "TrainingConfig":
        data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
        data["items"] = [TrainingItem(**item) for item in data["items"]]
        return cls(**data)


def training_caption(trigger_word: str, caption: str) -> str:
    """The text each image is trained on: the trigger word first, so prompts can invoke it."""
    parts = [part.strip() for part in (trigger_word, caption) if part.strip()]
    return ", ".join(parts)
