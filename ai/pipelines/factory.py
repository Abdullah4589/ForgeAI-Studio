"""Builds Diffusers pipelines for a model on disk.

Diffusers/torch are imported inside functions so the rest of the app runs without the AI extra.
"""

import importlib
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from ai.errors import DependencyMissingError, ModelLoadError, UnsupportedModelError
from ai.pipelines.registry import get_spec

logger = logging.getLogger(__name__)

SourceType = Literal["diffusers", "single_file"]


@dataclass(frozen=True)
class PipelineRequest:
    path: Path
    source_type: SourceType
    architecture: str
    device: Literal["cuda", "cpu"]
    enable_cpu_offload: bool


def import_diffusers() -> Any:
    try:
        return importlib.import_module("diffusers")
    except ImportError as exc:
        raise DependencyMissingError(
            'AI dependencies are not installed. Install them with: pip install -e ".[ai]"'
        ) from exc


def build_pipeline(request: PipelineRequest) -> Any:
    spec = get_spec(request.architecture)
    if spec is None:
        raise UnsupportedModelError(
            f"Model architecture '{request.architecture}' is not supported yet."
        )
    diffusers = import_diffusers()
    torch = importlib.import_module("torch")
    pipeline_cls = getattr(diffusers, spec.pipeline_class)
    # fp16 halves VRAM on GPU; most CPU kernels need fp32.
    dtype = torch.float16 if request.device == "cuda" else torch.float32

    try:
        if request.source_type == "diffusers":
            # use_safetensors=True refuses pickle-based .bin weights, which can execute code.
            pipe = pipeline_cls.from_pretrained(
                str(request.path), torch_dtype=dtype, use_safetensors=True
            )
        else:
            pipe = pipeline_cls.from_single_file(str(request.path), torch_dtype=dtype)
    except (OSError, ValueError, RuntimeError) as exc:
        logger.exception("pipeline_build_failed", extra={"path": str(request.path)})
        raise ModelLoadError(
            "The model could not be loaded. Check that it is a complete Diffusers folder or a "
            "valid .safetensors checkpoint with safetensors weights."
        ) from exc

    _apply_memory_optimisations(pipe, request)
    return pipe


def _apply_memory_optimisations(pipe: Any, request: PipelineRequest) -> None:
    # Diffusers uses PyTorch SDPA (memory-efficient attention) by default on torch>=2,
    # so no extra attention backend is needed.
    pipe.enable_attention_slicing()
    if hasattr(pipe, "enable_vae_slicing"):
        pipe.enable_vae_slicing()
    if request.device == "cuda" and request.enable_cpu_offload:
        # Offload keeps only the active submodule on the GPU; must not be combined with .to().
        pipe.enable_model_cpu_offload()
    else:
        pipe.to(request.device)
    pipe.set_progress_bar_config(disable=True)
