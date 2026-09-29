"""Builders for on-disk fixtures (fake model folders, synthetic safetensors files)."""

import json
import struct
from collections.abc import Mapping, Sequence
from pathlib import Path

SD15_LORA_TENSORS: dict[str, list[int]] = {
    "lora_unet_down_blocks_0_attentions_0_transformer_blocks_0_attn2_to_k.lora_down.weight": [
        4,
        768,
    ],
    "lora_unet_down_blocks_0_attentions_0_transformer_blocks_0_attn2_to_k.lora_up.weight": [320, 4],
}
SDXL_LORA_TENSORS: dict[str, list[int]] = {
    "lora_unet_input_blocks_4_1_transformer_blocks_0_attn2_to_k.lora_down.weight": [8, 2048],
    "lora_te2_text_model_encoder_layers_0_mlp_fc1.lora_down.weight": [8, 1280],
}


def write_safetensors(path: Path, tensors: Mapping[str, Sequence[int]]) -> Path:
    """Write a structurally valid safetensors file with zeroed float16 tensors."""
    header: dict[str, object] = {}
    offset = 0
    for name, shape in tensors.items():
        size = 2
        for dim in shape:
            size *= dim
        header[name] = {
            "dtype": "F16",
            "shape": list(shape),
            "data_offsets": [offset, offset + size],
        }
        offset += size
    raw = json.dumps(header).encode()
    path.write_bytes(struct.pack("<Q", len(raw)) + raw + b"\0" * offset)
    return path


def write_diffusers_model(directory: Path, name: str, class_name: str) -> Path:
    folder = directory / name
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "model_index.json").write_text(json.dumps({"_class_name": class_name}))
    return folder
