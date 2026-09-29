"""Supported model architectures.

Adding a model family means adding an entry here plus a loader branch in `factory.py`.
"""

from dataclasses import dataclass
from typing import Literal

Architecture = Literal["sd15", "sdxl", "unknown"]


@dataclass(frozen=True)
class ArchitectureSpec:
    key: Architecture
    label: str
    pipeline_class: str
    native_resolution: tuple[int, int]
    supported_resolutions: tuple[tuple[int, int], ...]
    # Hidden size of the text encoder, i.e. the input dim of UNet cross-attention key projections.
    # Used to recognise which base model a LoRA was trained for.
    cross_attention_dim: int


ARCHITECTURES: dict[str, ArchitectureSpec] = {
    "sd15": ArchitectureSpec(
        key="sd15",
        label="Stable Diffusion 1.x",
        pipeline_class="StableDiffusionPipeline",
        native_resolution=(512, 512),
        supported_resolutions=((512, 512), (512, 768), (768, 512)),
        cross_attention_dim=768,
    ),
    "sdxl": ArchitectureSpec(
        key="sdxl",
        label="Stable Diffusion XL",
        pipeline_class="StableDiffusionXLPipeline",
        native_resolution=(1024, 1024),
        supported_resolutions=((1024, 1024), (896, 1152), (1152, 896), (768, 1344), (1344, 768)),
        cross_attention_dim=2048,
    ),
}


def get_spec(architecture: str) -> ArchitectureSpec | None:
    return ARCHITECTURES.get(architecture)


def architecture_from_pipeline_class(class_name: str) -> Architecture:
    for spec in ARCHITECTURES.values():
        if spec.pipeline_class == class_name:
            return spec.key
    return "unknown"


def architecture_from_cross_attention_dim(dim: int) -> Architecture:
    for spec in ARCHITECTURES.values():
        if spec.cross_attention_dim == dim:
            return spec.key
    return "unknown"
