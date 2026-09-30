"""Florence-2 captioner (Microsoft, MIT licence) via Hugging Face Transformers.

Uses the natively supported `Florence2ForConditionalGeneration` class, so no model-repo code is
ever executed, and loads safetensors weights only.
"""

import importlib
import logging
import threading
import time
from pathlib import Path
from typing import Any, Literal

from PIL.Image import Image

from ai.device import release_memory
from ai.errors import DependencyMissingError, ModelLoadError

logger = logging.getLogger(__name__)

# One or two descriptive sentences: detailed enough for training, and short enough to fit
# CLIP's 77-token limit. "<MORE_DETAILED_CAPTION>" produced long, partly invented paragraphs.
TASK = "<DETAILED_CAPTION>"
MAX_NEW_TOKENS = 96
NUM_BEAMS = 3


class FlorenceCaptioner:
    def __init__(self, model_dir: Path, device: Literal["cuda", "cpu"]) -> None:
        self.name = model_dir.name
        self._model_dir = model_dir
        self._device = device
        self._model: Any = None
        self._processor: Any = None
        self._lock = threading.Lock()

    def caption(self, image: Image) -> str:
        with self._lock:
            model, processor = self._load()
            torch = importlib.import_module("torch")
            inputs = processor(text=TASK, images=image, return_tensors="pt")
            pixel_values = inputs["pixel_values"].to(self._device, dtype=model.dtype)
            with torch.inference_mode():
                ids = model.generate(
                    input_ids=inputs["input_ids"].to(self._device),
                    pixel_values=pixel_values,
                    max_new_tokens=MAX_NEW_TOKENS,
                    num_beams=NUM_BEAMS,
                    do_sample=False,
                )
            decoded = processor.batch_decode(ids, skip_special_tokens=False)[0]
            parsed = processor.post_process_generation(decoded, task=TASK, image_size=image.size)
            return str(parsed[TASK])

    def release(self) -> None:
        with self._lock:
            if self._model is None:
                return
            # Drop our references before collecting so the weights can actually be freed.
            self._model = None
            self._processor = None
            release_memory()
            logger.info("captioner_unloaded", extra={"model": self.name})

    def _load(self) -> tuple[Any, Any]:
        if self._model is not None:
            return self._model, self._processor
        if not (self._model_dir / "config.json").is_file():
            raise ModelLoadError(
                f"Caption model not found in {self._model_dir}. Download it with: "
                "python scripts/download_model.py --captioner"
            )
        try:
            transformers = importlib.import_module("transformers")
            torch = importlib.import_module("torch")
        except ImportError as exc:
            raise DependencyMissingError(
                'AI dependencies are not installed. Install them with: pip install -e ".[ai]"'
            ) from exc
        started = time.perf_counter()
        dtype = torch.float16 if self._device == "cuda" else torch.float32
        try:
            model = transformers.Florence2ForConditionalGeneration.from_pretrained(
                str(self._model_dir), dtype=dtype, use_safetensors=True
            )
            processor = transformers.AutoProcessor.from_pretrained(str(self._model_dir))
        except (OSError, ValueError) as exc:
            logger.exception("captioner_load_failed", extra={"model": self.name})
            raise ModelLoadError(
                "The caption model could not be loaded. Re-download it with: "
                "python scripts/download_model.py --captioner"
            ) from exc
        self._model = model.to(self._device).eval()
        self._processor = processor
        logger.info(
            "captioner_loaded",
            extra={
                "model": self.name,
                "device": self._device,
                "seconds": round(time.perf_counter() - started, 2),
            },
        )
        return self._model, self._processor
