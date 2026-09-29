from forge_api.schemas.common import ApiModel, ApiRequest, UtcDatetime


class ModelOut(ApiModel):
    id: int
    name: str
    path: str
    source_type: str
    architecture: str
    file_size_bytes: int
    description: str
    preview_image_path: str | None
    supported_resolutions: list[list[int]]
    available: bool
    loaded: bool = False
    created_at: UtcDatetime


class ModelLoadRequest(ApiRequest):
    model_id: int


class ModelStatusOut(ApiModel):
    loaded_model_id: int | None
