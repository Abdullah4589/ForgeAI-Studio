from typing import Any, Literal

from pydantic import Field, computed_field

from forge_api.schemas.common import ApiModel, UtcDatetime


class GenerationImageOut(ApiModel):
    id: int
    index: int
    seed: int
    width: int
    height: int
    file_size_bytes: int

    @computed_field  # type: ignore[prop-decorator]
    @property
    def url(self) -> str:
        return f"/api/images/{self.id}"


class GenerationOut(ApiModel):
    id: int
    created_at: UtcDatetime
    prompt: str
    negative_prompt: str
    model_id: int | None
    model_name: str
    lora_id: int | None
    lora_name: str | None
    lora_strength: float | None
    seed: int
    width: int
    height: int
    steps: int
    guidance_scale: float
    num_images: int
    duration_ms: int
    device: str
    # Stored as `model_config` in the DB; renamed because pydantic reserves that attribute.
    pipeline_config: dict[str, Any] = Field(validation_alias="model_config_json")
    images: list[GenerationImageOut]


class HistoryPage(ApiModel):
    items: list[GenerationOut]
    total: int
    page: int
    page_size: int


SortOrder = Literal["newest", "oldest"]
