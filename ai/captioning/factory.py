from pathlib import Path
from typing import Literal

from ai.captioning.florence import FlorenceCaptioner
from ai.captioning.mock import MockCaptioner
from ai.captioning.types import Captioner


def create_captioner(
    kind: Literal["florence", "mock"],
    *,
    model_dir: Path,
    device: Literal["cuda", "cpu"],
    mock_delay_seconds: float = 0.0,
) -> Captioner:
    if kind == "mock":
        return MockCaptioner(delay_seconds=mock_delay_seconds)
    return FlorenceCaptioner(model_dir, device)
