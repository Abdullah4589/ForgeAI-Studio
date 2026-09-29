from pydantic import Field

from forge_api.schemas.common import ApiModel, ApiRequest, UtcDatetime


class LoraOut(ApiModel):
    id: int
    name: str
    filename: str
    file_size_bytes: int
    base_architecture: str
    rank: int | None
    enabled: bool
    default_strength: float
    trigger_words: str
    description: str
    preview_image_path: str | None
    available: bool
    created_at: UtcDatetime


class LoraUpdate(ApiRequest):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    enabled: bool | None = None
    default_strength: float | None = Field(default=None, ge=-2, le=2)
    trigger_words: str | None = Field(default=None, max_length=1000)
    description: str | None = Field(default=None, max_length=5000)
