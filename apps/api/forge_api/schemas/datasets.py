from typing import Annotated, Literal

from pydantic import Field, computed_field

from forge_api.schemas.common import ApiModel, ApiRequest, UtcDatetime

TargetResolution = Annotated[int, Field(ge=256, le=2048, multiple_of=8)]
QualityFlag = Literal["low_resolution", "extreme_aspect_ratio", "possibly_blurry", "near_duplicate"]


class DatasetCreate(ApiRequest):
    name: str = Field(min_length=1, max_length=255)
    description: str = Field(default="", max_length=5000)
    target_resolution: TargetResolution = 512


class DatasetUpdate(ApiRequest):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=5000)
    target_resolution: TargetResolution | None = None


class CaptionUpdate(ApiRequest):
    caption: str = Field(max_length=5000)


class ReorderRequest(ApiRequest):
    # Every image id of the dataset exactly once, in the new order.
    image_ids: list[int] = Field(max_length=10_000)


class DatasetImageOut(ApiModel):
    id: int
    dataset_id: int
    position: int
    original_filename: str
    format: str
    width: int
    height: int
    file_size_bytes: int
    blur_score: float
    caption: str
    caption_source: str | None
    caption_updated_at: UtcDatetime | None
    created_at: UtcDatetime
    # Derived when read, so they always reflect the current dataset settings and contents.
    flags: list[QualityFlag]
    near_duplicate_of: list[int]

    @computed_field  # type: ignore[prop-decorator]
    @property
    def url(self) -> str:
        return f"/api/datasets/{self.dataset_id}/images/{self.id}/file"

    @computed_field  # type: ignore[prop-decorator]
    @property
    def thumbnail_url(self) -> str:
        return f"/api/datasets/{self.dataset_id}/images/{self.id}/thumbnail"


class DatasetSummary(ApiModel):
    id: int
    name: str
    description: str
    target_resolution: int
    created_at: UtcDatetime
    updated_at: UtcDatetime
    image_count: int
    flagged_count: int
    uncaptioned_count: int
    cover_thumbnail_url: str | None


class DatasetOut(DatasetSummary):
    images: list[DatasetImageOut]


class SkippedUpload(ApiModel):
    filename: str
    reason: Literal[
        "duplicate",
        "not_an_image",
        "unsupported_format",
        "too_many_pixels",
        "corrupt",
        "too_large",
        "dataset_full",
    ]
    message: str


class UploadResult(ApiModel):
    added: list[DatasetImageOut]
    skipped: list[SkippedUpload]
