import shutil

import psutil

from ai.device import gpu_info
from forge_api.container import AppServices
from forge_api.schemas.system import SystemOut


def system_status(services: AppServices) -> SystemOut:
    gpu = gpu_info()
    memory = psutil.virtual_memory()
    output_dir = services.settings.output_directory
    disk = shutil.disk_usage(output_dir if output_dir.exists() else ".")
    return SystemOut(
        torch_installed=gpu.torch_installed,
        torch_version=gpu.torch_version,
        cuda_available=gpu.cuda_available,
        cuda_version=gpu.cuda_version,
        gpu_name=gpu.gpu_name,
        vram_total_bytes=gpu.vram_total_bytes,
        vram_used_bytes=gpu.vram_used_bytes,
        vram_free_bytes=gpu.vram_free_bytes,
        device=services.device,
        generation_backend=services.settings.generation_backend,
        # A short interval gives a real reading instead of the meaningless first-call 0.0.
        cpu_percent=psutil.cpu_percent(interval=0.1),
        cpu_count=psutil.cpu_count(),
        ram_total_bytes=memory.total,
        ram_used_bytes=memory.used,
        ram_available_bytes=memory.available,
        disk_total_bytes=disk.total,
        disk_used_bytes=disk.used,
        disk_free_bytes=disk.free,
    )
