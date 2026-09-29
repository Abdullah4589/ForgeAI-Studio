from forge_api.schemas.common import ApiModel


class SystemOut(ApiModel):
    torch_installed: bool
    torch_version: str | None
    cuda_available: bool
    cuda_version: str | None
    gpu_name: str | None
    vram_total_bytes: int | None
    vram_used_bytes: int | None
    vram_free_bytes: int | None
    device: str
    generation_backend: str
    cpu_percent: float
    cpu_count: int | None
    ram_total_bytes: int
    ram_used_bytes: int
    ram_available_bytes: int
    disk_total_bytes: int
    disk_used_bytes: int
    disk_free_bytes: int
