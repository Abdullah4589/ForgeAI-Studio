"""Stand-in trainer for tests, CI and UI work without PyTorch or model weights.

Selected only when TRAINING_BACKEND=mock. It walks through the same phases and events as the
real trainer and writes a structurally valid SD 1.x LoRA (zero weights) plus sample images, so
the worker process, persistence, LoRA registration and UI can all be exercised end to end.
A LoRA name of MOCK_FAIL_NAME makes it fail, to exercise error handling.
"""

import json
import math
import struct
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

import psutil
from PIL import Image, ImageDraw

from ai.training.config import TrainingConfig
from ai.training.errors import TrainingCancelled, TrainingFailedError

MOCK_FAIL_NAME = "mock-fail"

Emit = Callable[..., None]


def train(config: TrainingConfig, emit: Emit, should_cancel: Callable[[], bool]) -> Path:
    output = Path(config.output_dir)
    output.mkdir(parents=True, exist_ok=True)
    emit("status", message="Loading model")
    emit("status", message=f"Preparing {len(config.items)} images")
    if config.name == MOCK_FAIL_NAME:
        raise TrainingFailedError("Mock training failed on purpose.")

    started = time.perf_counter()
    last_checkpoint: str | None = None
    for step in range(1, config.steps + 1):
        if should_cancel():
            raise TrainingCancelled(last_checkpoint)
        if config.mock_step_delay_seconds:
            time.sleep(config.mock_step_delay_seconds)
        # A plausible, deterministic loss curve: decaying with some wobble.
        loss = 0.05 + 0.15 * math.exp(-step / 40) + 0.02 * abs(math.sin(step))
        emit(
            "progress",
            step=step,
            total=config.steps,
            loss=round(loss, 5),
            elapsed=round(time.perf_counter() - started, 3),
            memory_bytes=psutil.Process().memory_info().rss,
        )
        if config.save_every and step % config.save_every == 0 and step < config.steps:
            path = output / "checkpoints" / f"{config.name}-step-{step:06d}.safetensors"
            write_mock_lora(path, config.rank)
            last_checkpoint = str(path)
            emit("checkpoint", step=step, path=str(path))

    final = output / f"{config.name}.safetensors"
    write_mock_lora(final, config.rank)
    emit(
        "saved",
        path=str(final),
        avg_step_seconds=round((time.perf_counter() - started) / config.steps, 3),
    )

    if config.sample_count:
        emit("status", message="Generating samples")
    for index in range(config.sample_count):
        if should_cancel():
            break  # the LoRA is already saved; stop sampling only
        path = output / "samples" / f"sample-{index + 1}.png"
        path.parent.mkdir(parents=True, exist_ok=True)
        _sample_image(config.resolution, config.seed + index).save(path)
        emit("sample", index=index, path=str(path), safety_blocked=False)
    return final


def write_mock_lora(path: Path, rank: int) -> None:
    """A tiny PEFT/diffusers-format SD 1.x LoRA with zero weights."""
    prefix = "unet.down_blocks.0.attentions.0.transformer_blocks.0.attn2.to_k"
    shapes = {f"{prefix}.lora_A.weight": [rank, 768], f"{prefix}.lora_B.weight": [320, rank]}
    header: dict[str, Any] = {}
    offset = 0
    for name, shape in shapes.items():
        size = 4 * shape[0] * shape[1]
        header[name] = {"dtype": "F32", "shape": shape, "data_offsets": [offset, offset + size]}
        offset += size
    raw = json.dumps(header).encode()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(struct.pack("<Q", len(raw)) + raw + b"\0" * offset)


def _sample_image(size: int, seed: int) -> Image.Image:
    image = Image.new("RGB", (size, size), ((seed * 53) % 256, (seed * 97) % 256, 160))
    ImageDraw.Draw(image).text((8, 8), f"MOCK SAMPLE seed={seed}", fill=(255, 255, 255))
    return image
