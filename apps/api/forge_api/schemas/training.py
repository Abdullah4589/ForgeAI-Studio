from typing import Literal

from pydantic import Field, computed_field

from ai.generation.types import MAX_SEED
from forge_api.schemas.common import ApiModel, ApiRequest, UtcDatetime
from forge_api.schemas.generation import JobOut


# Kept in sync with apps/web/src/lib/training.ts.
class TrainingRequest(ApiRequest):
    dataset_id: int
    base_model_id: int
    # Becomes the LoRA file name; sanitised by the server.
    name: str = Field(min_length=1, max_length=100)
    trigger_word: str = Field(default="", max_length=100)
    resolution: Literal[256, 512, 768] = 512
    rank: int = Field(default=8, ge=1, le=128)
    alpha: float = Field(default=8, gt=0, le=256)
    learning_rate: float = Field(default=1e-4, ge=1e-6, le=1e-2)
    batch_size: int = Field(default=1, ge=1, le=8)
    steps: int = Field(default=500, ge=1, le=20_000)
    # 0 disables intermediate checkpoints.
    save_every: int = Field(default=0, ge=0, le=20_000)
    seed: int | None = Field(default=None, ge=0, le=MAX_SEED)
    sample_count: int = Field(default=2, ge=0, le=4)
    sample_steps: int = Field(default=20, ge=1, le=50)


class TrainingSample(ApiModel):
    index: int
    safety_blocked: bool


class TrainingRunOut(ApiModel):
    id: int
    created_at: UtcDatetime
    name: str
    dataset_id: int | None
    dataset_name: str
    base_model_id: int | None
    base_model_name: str
    trigger_word: str
    resolution: int
    rank: int
    alpha: float
    learning_rate: float
    batch_size: int
    steps: int
    save_every: int
    seed: int
    sample_count: int
    sample_steps: int
    image_count: int
    status: str
    job_id: str | None
    current_step: int
    last_loss: float | None
    loss_history: list[list[float]]
    peak_memory_bytes: int | None
    avg_step_seconds: float | None
    started_at: UtcDatetime | None
    finished_at: UtcDatetime | None
    error_message: str | None
    lora_id: int | None
    has_checkpoint: bool
    samples: list[TrainingSample]

    @computed_field  # type: ignore[prop-decorator]
    @property
    def sample_urls(self) -> list[str]:
        return [f"/api/training/{self.id}/samples/{s.index}" for s in self.samples]


class TrainingJobOut(JobOut):
    run_id: int
