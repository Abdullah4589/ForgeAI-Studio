"""Deterministic captioner for tests, CI and UI work without model weights.

Selected only when CAPTION_BACKEND=mock. Captions are derived from the image itself (size and
average colour) so they are stable and differ between images.
"""

import time

from PIL import ImageStat
from PIL.Image import Image

_COLOURS = {
    "red": (200, 60, 60),
    "green": (60, 160, 80),
    "blue": (60, 90, 200),
    "yellow": (220, 200, 70),
    "grey": (128, 128, 128),
    "black": (20, 20, 20),
    "white": (235, 235, 235),
}


class MockCaptioner:
    name = "mock"

    def __init__(self, delay_seconds: float = 0.0) -> None:
        self._delay = delay_seconds

    def caption(self, image: Image) -> str:
        if self._delay:
            time.sleep(self._delay)
        mean = ImageStat.Stat(image.convert("RGB")).mean
        colour = min(
            _COLOURS,
            key=lambda name: sum((a - b) ** 2 for a, b in zip(mean, _COLOURS[name], strict=True)),
        )
        return f"The image shows a mock caption of a {image.width}x{image.height} {colour} picture."

    def release(self) -> None:
        return None
