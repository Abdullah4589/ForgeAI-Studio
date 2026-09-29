from typing import Annotated, Any

from pydantic import Field

from ai.generation.types import MAX_SEED
from forge_api.schemas.common import ApiModel, ApiRequest

# Diffusion latents are 1/8 of image size, so dimensions must be multiples of 8.
ImageSize = Annotated[int, Field(ge=256, le=1536, multiple_of=8)]
Steps = Annotated[int, Field(ge=1, le=150)]
GuidanceScale = Annotated[float, Field(ge=0, le=30)]
ImageCount = Annotated[int, Field(ge=1, le=4)]
NegativePrompt = Annotated[str, Field(max_length=2000)]


class GenerateRequest(ApiRequest):
    model_id: int
    prompt: str = Field(min_length=1, max_length=2000)
    negative_prompt: NegativePrompt = ""
    lora_id: int | None = None
    lora_strength: float = Field(default=1.0, ge=-2, le=2)
    width: ImageSize = 512
    height: ImageSize = 512
    steps: Steps = 25
    guidance_scale: GuidanceScale = 7.5
    seed: int | None = Field(default=None, ge=0, le=MAX_SEED)
    num_images: ImageCount = 1


class CancelRequest(ApiRequest):
    job_id: str = Field(min_length=1, max_length=64)


class JobOut(ApiModel):
    id: str
    kind: str
    status: str
    step: int
    total_steps: int
    message: str
    created_at: float
    started_at: float | None
    finished_at: float | None
    result: dict[str, Any] | None
    error: dict[str, str] | None
