"""Device selection, GPU introspection and memory cleanup.

PyTorch is an optional dependency, so it is imported lazily and every function works without it.
"""

import gc
import importlib
import logging
import os
import sys
from dataclasses import dataclass
from types import ModuleType
from typing import Any, Literal

logger = logging.getLogger(__name__)

DevicePreference = Literal["auto", "cuda", "cpu"]

# OpenBLAS/MKL size a workspace from the thread count at library load. One pool per
# core can exhaust the commit limit on an 8GB machine before a single image is denoised.
_THREAD_ENV_VARS = ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS")
_CPU_THREAD_CAP = 4
_interop_capped = False


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


def _apply_thread_env_cap() -> None:
    for name in _THREAD_ENV_VARS:
        os.environ.setdefault(name, str(_CPU_THREAD_CAP))


def _cpu_thread_count() -> int:
    raw = os.environ.get("OMP_NUM_THREADS", str(_CPU_THREAD_CAP))
    try:
        count = int(raw)
    except ValueError:
        return _CPU_THREAD_CAP
    return count if count > 0 else _CPU_THREAD_CAP


def limit_cpu_threads(torch: Any | None = None) -> None:
    """Cap OpenMP/BLAS pools. Environment variables only help if set before torch loads."""
    global _interop_capped
    _apply_thread_env_cap()
    if torch is None:
        torch = sys.modules.get("torch")
    if torch is None:
        return
    count = _cpu_thread_count()
    set_threads = getattr(torch, "set_num_threads", None)
    if callable(set_threads):
        set_threads(count)
    if _interop_capped:
        return
    set_interop = getattr(torch, "set_num_interop_threads", None)
    if not callable(set_interop):
        return
    try:
        set_interop(1)
    except RuntimeError:
        logger.debug("cpu_interop_threads_already_set")
    _interop_capped = True


# Apply as soon as this module is imported. The API and the training worker both import
# `ai.device` before they import torch, which is when the native libraries read the cap.
_apply_thread_env_cap()


def _cuda_is_available(torch: Any) -> bool:
    is_available = getattr(getattr(torch, "cuda", None), "is_available", None)
    if not callable(is_available):
        return False
    try:
        return bool(is_available())
    except RuntimeError:
        logger.warning("cuda_availability_check_failed")
        return False


def load_torch() -> ModuleType | None:
    _apply_thread_env_cap()
    try:
        torch = importlib.import_module("torch")
    except ImportError:
        return None
    if not _cuda_is_available(torch):
        limit_cpu_threads(torch)
    return torch


def cuda_available() -> bool:
    torch = load_torch()
    return torch is not None and _cuda_is_available(torch)


def resolve_device(preference: DevicePreference) -> Literal["cuda", "cpu"]:
    """Pick the compute device, falling back to CPU instead of failing when CUDA is absent."""
    has_cuda = cuda_available()
    if preference == "cuda" and not has_cuda:
        logger.warning("cuda_requested_but_unavailable", extra={"fallback": "cpu"})
        chosen: Literal["cuda", "cpu"] = "cpu"
    elif preference == "cpu" or not has_cuda:
        chosen = "cpu"
    else:
        chosen = "cuda"
    # `DEVICE=cpu` still runs the whole UNet on the CPU even when a GPU is present.
    if chosen == "cpu":
        limit_cpu_threads(load_torch())
    return chosen


def gpu_info() -> GpuInfo:
    torch = load_torch()
    if torch is None:
        return GpuInfo(False, None, False, None, None, None, None, None)
    if not _cuda_is_available(torch):
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
