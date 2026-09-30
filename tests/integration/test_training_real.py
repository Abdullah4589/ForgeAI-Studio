"""Opt-in check of real LoRA training (PyTorch + a local SD 1.x model); skipped in CI.

Run with:  FORGE_REAL_TRAINING=1 pytest tests/integration/test_training_real.py
Uses storage/models/bk-sdm-tiny (python scripts/download_model.py). Takes ~1-2 minutes on CPU.
"""

import importlib.util
import os
import threading
from pathlib import Path

import pytest

from ai.lora.inspect import inspect_lora
from ai.training.config import TrainingConfig, TrainingItem
from ai.training.runner import run_worker
from tests.helpers import encode, picture

MODEL = Path(__file__).resolve().parents[2] / "storage" / "models" / "bk-sdm-tiny"

pytestmark = pytest.mark.skipif(
    os.environ.get("FORGE_REAL_TRAINING") != "1"
    or importlib.util.find_spec("torch") is None
    or not (MODEL / "model_index.json").is_file(),
    reason="set FORGE_REAL_TRAINING=1 with the [ai] extra and bk-sdm-tiny installed",
)


def test_real_training_produces_a_loadable_lora(tmp_path: Path) -> None:
    images = []
    for index in range(2):
        path = tmp_path / f"{index}.png"
        path.write_bytes(encode(picture(index, (256, 256))))
        images.append(TrainingItem(str(path), f"fgx, coloured rectangles {index}"))
    config = TrainingConfig(
        backend="diffusers",
        model_path=str(MODEL),
        source_type="diffusers",
        architecture="sd15",
        output_dir=str(tmp_path / "out"),
        name="real-test",
        items=images,
        resolution=256,
        rank=4,
        alpha=8,
        learning_rate=1e-4,
        batch_size=2,
        steps=2,
        save_every=0,
        seed=1,
        device="cpu",
        sample_count=0,
    )
    progress: list[float] = []
    outcome = run_worker(
        config,
        tmp_path / "run",
        lambda e: progress.append(e["loss"]) if e["type"] == "progress" else None,
        threading.Event(),
    )
    assert outcome.status == "completed", outcome.error
    assert len(progress) == 2 and all(loss > 0 for loss in progress)
    info = inspect_lora(Path(str(outcome.lora_path)))
    assert (info.architecture, info.rank) == ("sd15", 4)
