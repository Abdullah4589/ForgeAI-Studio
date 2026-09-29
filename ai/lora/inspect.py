"""Validates LoRA files and infers which base architecture they target."""

from dataclasses import dataclass
from pathlib import Path

from ai.errors import InvalidLoraError, InvalidSafetensorsError
from ai.pipelines.registry import Architecture, architecture_from_cross_attention_dim
from ai.safetensors_header import TensorInfo, read_header

# Naming conventions used by kohya-ss, diffusers/PEFT and older diffusers LoRA exports.
_LORA_DOWN_MARKERS = ("lora_down", "lora_A", "lora.down")
_SDXL_TEXT_ENCODER_2_MARKERS = ("lora_te2_", "text_encoder_2.")


@dataclass(frozen=True)
class LoraInfo:
    architecture: Architecture
    tensor_count: int
    rank: int | None


def inspect_lora(path: Path) -> LoraInfo:
    try:
        tensors = read_header(path)
    except InvalidSafetensorsError as exc:
        raise InvalidLoraError(exc.message) from exc
    down_weights = {
        name: info
        for name, info in tensors.items()
        if any(marker in name for marker in _LORA_DOWN_MARKERS)
    }
    if not down_weights:
        raise InvalidLoraError("This file does not look like a LoRA adapter (no LoRA weights).")
    return LoraInfo(
        architecture=detect_lora_architecture(tensors),
        tensor_count=len(tensors),
        rank=_rank(down_weights),
    )


def detect_lora_architecture(tensors: dict[str, TensorInfo]) -> Architecture:
    names = tensors.keys()
    if any(marker in name for name in names for marker in _SDXL_TEXT_ENCODER_2_MARKERS):
        return "sdxl"
    # The input width of a cross-attention key projection equals the text encoder hidden size,
    # which differs per base model family (768 for SD1.x, 2048 for SDXL).
    for name, info in tensors.items():
        is_cross_attn_key = "attn2" in name and "to_k" in name
        if (
            is_cross_attn_key
            and any(m in name for m in _LORA_DOWN_MARKERS)
            and len(info.shape) == 2
        ):
            return architecture_from_cross_attention_dim(info.shape[1])
    return "unknown"


def is_compatible(lora_architecture: str, model_architecture: str) -> bool:
    """Unknown LoRAs are allowed through; loading will fail loudly if they truly mismatch."""
    return lora_architecture in ("unknown", model_architecture)


def _rank(down_weights: dict[str, TensorInfo]) -> int | None:
    for info in down_weights.values():
        if info.shape:
            return info.shape[0]
    return None
