"""Attaches and detaches LoRA adapters on a loaded Diffusers pipeline (via PEFT)."""

import logging
from pathlib import Path
from typing import Any

from ai.errors import IncompatibleLoraError

logger = logging.getLogger(__name__)

ADAPTER_NAME = "forge_active"


def apply_lora(pipe: Any, path: Path, strength: float) -> None:
    try:
        pipe.load_lora_weights(str(path.parent), weight_name=path.name, adapter_name=ADAPTER_NAME)
        pipe.set_adapters([ADAPTER_NAME], adapter_weights=[strength])
    except (ValueError, RuntimeError, KeyError) as exc:
        logger.exception("lora_apply_failed", extra={"path": str(path)})
        # Leave the pipeline clean so the next generation isn't affected by a half-loaded adapter.
        remove_loras(pipe)
        raise IncompatibleLoraError(
            "This LoRA could not be applied to the selected model. It was probably trained for "
            "a different base model."
        ) from exc
    logger.info("lora_applied", extra={"path": str(path), "strength": strength})


def remove_loras(pipe: Any) -> bool:
    """Returns False if the pipeline may still carry adapter weights and should be reloaded."""
    try:
        pipe.unload_lora_weights()
    except (ValueError, RuntimeError):
        logger.exception("lora_remove_failed")
        return False
    return True
