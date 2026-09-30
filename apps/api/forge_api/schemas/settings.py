from forge_api.schemas.common import ApiModel, ApiRequest
from forge_api.schemas.generation import (
    GuidanceScale,
    ImageCount,
    ImageSize,
    NegativePrompt,
    Steps,
)


class GenerationDefaults(ApiRequest):
    negative_prompt: NegativePrompt = ""
    width: ImageSize = 512
    height: ImageSize = 512
    steps: Steps = 25
    guidance_scale: GuidanceScale = 7.5
    num_images: ImageCount = 1


class RuntimeConfigOut(ApiModel):
    model_directory: str
    lora_directory: str
    output_directory: str
    dataset_directory: str
    device: str
    generation_backend: str
    caption_backend: str
    caption_model_directory: str
    enable_cpu_offload: bool
    model_idle_unload_seconds: int
    max_upload_size_mb: int


class SettingsOut(ApiModel):
    runtime: RuntimeConfigOut
    generation_defaults: GenerationDefaults
