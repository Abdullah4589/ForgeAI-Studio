from typing import Literal

from pydantic import Field

from forge_api.schemas.common import ApiRequest
from forge_api.schemas.generation import JobOut

# empty_only: fill in missing captions only.
# replace_ai: also regenerate captions an earlier AI run wrote.
# everything: also overwrite manual captions (clients must confirm with the user first).
OverwriteMode = Literal["empty_only", "replace_ai", "everything"]


class CaptionRequest(ApiRequest):
    # Omit to consider every image in the dataset.
    image_ids: list[int] | None = Field(default=None, min_length=1, max_length=1000)
    overwrite: OverwriteMode = "empty_only"


class CaptionJobOut(JobOut):
    queued: int
    skipped_manual: int
    skipped_existing: int
