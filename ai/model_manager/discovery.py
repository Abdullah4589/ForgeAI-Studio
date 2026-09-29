"""Finds installed base models in the model directory without loading them."""

import json
import logging
import re
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from ai.errors import InvalidSafetensorsError
from ai.pipelines.factory import SourceType
from ai.pipelines.registry import (
    Architecture,
    architecture_from_pipeline_class,
    get_spec,
)
from ai.safetensors_header import read_header

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class DiscoveredModel:
    name: str
    path: Path
    source_type: SourceType
    architecture: Architecture
    size_bytes: int
    supported_resolutions: list[tuple[int, int]]


def scan_models(directory: Path) -> list[DiscoveredModel]:
    """Return models found directly inside `directory` (one level deep)."""
    if not directory.is_dir():
        return []
    found: list[DiscoveredModel] = []
    for entry in sorted(directory.iterdir()):
        if entry.is_dir() and (entry / "model_index.json").is_file():
            found.append(_describe_diffusers_folder(entry))
        elif entry.is_file() and entry.suffix.lower() == ".safetensors":
            model = _describe_single_file(entry)
            if model is not None:
                found.append(model)
    return found


def _describe_diffusers_folder(folder: Path) -> DiscoveredModel:
    try:
        index = json.loads((folder / "model_index.json").read_text(encoding="utf-8"))
        class_name = str(index.get("_class_name", ""))
    except (OSError, json.JSONDecodeError, AttributeError):
        logger.warning("model_index_unreadable", extra={"path": str(folder)})
        class_name = ""
    architecture = architecture_from_pipeline_class(class_name)
    return _build(folder, "diffusers", architecture, _folder_size(folder))


def _folder_size(folder: Path) -> int:
    """Total size of model files, ignoring hidden folders such as Hugging Face's `.cache/`."""
    return sum(
        path.stat().st_size
        for path in folder.rglob("*")
        if path.is_file()
        and not any(part.startswith(".") for part in path.relative_to(folder).parts)
    )


def _describe_single_file(path: Path) -> DiscoveredModel | None:
    try:
        keys = read_header(path).keys()
    except InvalidSafetensorsError:
        logger.warning("model_file_invalid", extra={"path": str(path)})
        return None
    return _build(path, "single_file", detect_checkpoint_architecture(keys), path.stat().st_size)


def detect_checkpoint_architecture(keys: Iterable[str]) -> Architecture:
    """Recognise original (non-diffusers) Stable Diffusion checkpoints by their tensor names."""
    names = list(keys)
    if any(k.startswith("conditioner.embedders.1.") for k in names):
        return "sdxl"
    if any(k.startswith("cond_stage_model.transformer.") for k in names):
        return "sd15"
    return "unknown"


def _build(path: Path, source: SourceType, arch: Architecture, size: int) -> DiscoveredModel:
    spec = get_spec(arch)
    resolutions = list(spec.supported_resolutions) if spec else []
    return DiscoveredModel(
        name=_display_name(path),
        path=path,
        source_type=source,
        architecture=arch,
        size_bytes=size,
        supported_resolutions=resolutions,
    )


def _display_name(path: Path) -> str:
    stem = path.name.removesuffix(".safetensors")
    return re.sub(r"[-_]+", " ", stem).strip() or path.name
