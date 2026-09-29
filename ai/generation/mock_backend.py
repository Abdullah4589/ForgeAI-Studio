"""Deterministic stand-in backend for tests, CI and UI development without model weights.

It never touches a model: it draws a seed-derived gradient so the rest of the system (jobs,
progress, cancellation, persistence, history) can be exercised end-to-end. Selected only when
GENERATION_BACKEND=mock.

A prompt containing MOCK_BLOCKED_TOKEN simulates the safety checker blocking the first image, so
tests can exercise that path without real weights.
"""

import random
import time

from PIL import Image, ImageDraw

from ai.errors import GenerationCancelledError
from ai.generation.types import (
    CancelToken,
    GenerationOutput,
    GenerationParams,
    ModelRef,
    ProgressCallback,
)

MOCK_BLOCKED_TOKEN = "mock:blocked"


class MockBackend:
    def __init__(self, step_delay_seconds: float = 0.0) -> None:
        self._step_delay = step_delay_seconds

    def generate(
        self, params: GenerationParams, on_progress: ProgressCallback, cancel: CancelToken
    ) -> GenerationOutput:
        for step in range(1, params.steps + 1):
            if cancel.is_set():
                raise GenerationCancelledError()
            if self._step_delay:
                time.sleep(self._step_delay)
            on_progress(step, params.steps)
        seeds = [params.image_seed(i) for i in range(params.num_images)]
        images = [_render(params.width, params.height, seed) for seed in seeds]
        blocked = [MOCK_BLOCKED_TOKEN in params.prompt and i == 0 for i in range(len(images))]
        return GenerationOutput(
            images=[_black(im) if b else im for im, b in zip(images, blocked, strict=True)],
            safety_blocked=blocked,
            seeds=seeds,
            device="mock",
            model_config={"backend": "mock"},
        )

    def preload(self, model: ModelRef) -> None:
        return None  # nothing to load

    def release(self) -> None:
        return None


def _black(image: Image.Image) -> Image.Image:
    # Mirrors Diffusers, which returns an all-black image in place of a flagged one.
    return Image.new("RGB", image.size)


def _render(width: int, height: int, seed: int) -> Image.Image:
    rng = random.Random(seed)
    start = tuple(rng.randrange(256) for _ in range(3))
    end = tuple(rng.randrange(256) for _ in range(3))
    image = Image.new("RGB", (width, height))
    draw = ImageDraw.Draw(image)
    for y in range(height):
        t = y / max(height - 1, 1)
        colour = tuple(round(a + (b - a) * t) for a, b in zip(start, end, strict=True))
        draw.line([(0, y), (width, y)], fill=colour)
    draw.text((12, 12), f"MOCK seed={seed}", fill=(255, 255, 255))
    return image
