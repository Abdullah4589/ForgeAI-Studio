"""Device selection, GPU introspection and memory cleanup.

PyTorch is an optional dependency, so it is imported lazily and every function works without it.
"""

import gc
import importlib
import logging
from dataclasses import dataclass
from types import ModuleType
from typing import Literal

logger = logging.getLogger(__name__)

DevicePreference = Literal["auto", "cuda", "cpu"]


@dataclass(frozen=True)
class GpuInfo:
    torch_installed: bool
    torch_version: str | None
    cuda_available: bool
    cuda_version: str | None
    gpu_name: str | None
    vram_total_bytes: int | None
    vram_used_bytes: int | None
    vram_free_bytes: int | None


def load_torch() -> ModuleType | None:
    try:
        return importlib.import_module("torch")
    except ImportError:
        return None


def cuda_available() -> bool:
    torch = load_torch()
    return bool(torch is not None and torch.cuda.is_available())


def resolve_device(preference: DevicePreference) -> Literal["cuda", "cpu"]:
    """Pick the compute device, falling back to CPU instead of failing when CUDA is absent."""
    has_cuda = cuda_available()
    if preference == "cuda" and not has_cuda:
        logger.warning("cuda_requested_but_unavailable", extra={"fallback": "cpu"})
        return "cpu"
    if preference == "cpu":
        return "cpu"
    return "cuda" if has_cuda else "cpu"


def gpu_info() -> GpuInfo:
    torch = load_torch()
    if torch is None:
        return GpuInfo(False, None, False, None, None, None, None, None)
    if not torch.cuda.is_available():
        return GpuInfo(True, str(torch.__version__), False, None, None, None, None, None)
    try:
        free, total = torch.cuda.mem_get_info()
        name = torch.cuda.get_device_name(0)
    except RuntimeError:
        # A broken driver shouldn't take down the System page.
        logger.exception("cuda_introspection_failed")
        return GpuInfo(
            True, str(torch.__version__), True, torch.version.cuda, None, None, None, None
        )
    return GpuInfo(
        torch_installed=True,
        torch_version=str(torch.__version__),
        cuda_available=True,
        cuda_version=torch.version.cuda,
        gpu_name=name,
        vram_total_bytes=int(total),
        vram_used_bytes=int(total - free),
        vram_free_bytes=int(free),
    )


def release_memory() -> None:
    """Drop unreferenced tensors and return cached CUDA blocks to the driver."""
    gc.collect()
    torch = load_torch()
    if torch is not None and torch.cuda.is_available():
        torch.cuda.empty_cache()
