"""Builders for on-disk fixtures (fake model folders, synthetic safetensors files)."""

import io
import json
import random
import struct
from collections.abc import Mapping, Sequence
from pathlib import Path

from PIL import Image, ImageDraw

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


def picture(seed: int, size: tuple[int, int] = (512, 512)) -> Image.Image:
    """A structured test picture (random coloured rectangles) with strong, distinct edges."""
    rng = random.Random(seed)
    image = Image.new("RGB", size, tuple(rng.randrange(256) for _ in range(3)))
    draw = ImageDraw.Draw(image)
    for _ in range(12):
        x0, y0 = rng.randrange(size[0]), rng.randrange(size[1])
        x1 = x0 + rng.randrange(size[0] // 8, size[0] // 2 + 1)
        y1 = y0 + rng.randrange(size[1] // 8, size[1] // 2 + 1)
        draw.rectangle((x0, y0, x1, y1), fill=tuple(rng.randrange(256) for _ in range(3)))
    return image


def encode(image: Image.Image, fmt: str = "PNG", **options: object) -> bytes:
    out = io.BytesIO()
    image.save(out, format=fmt, **options)
    return out.getvalue()
