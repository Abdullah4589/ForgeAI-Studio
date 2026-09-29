from typing import Annotated, Literal

from pydantic import Field, model_validator

from ai.generation.types import MAX_SEED
from forge_api.schemas.common import ApiModel, ApiRequest, UtcDatetime
from forge_api.schemas.generation import GuidanceScale, ImageSize, NegativePrompt, Steps
from forge_api.schemas.history import GenerationOut

MIN_CELLS, MAX_CELLS = 2, 6

LoraStrength = Annotated[float, Field(ge=-2, le=2)]
Seed = Annotated[int, Field(ge=0, le=MAX_SEED)]


class LoraStrengthAxis(ApiRequest):
    kind: Literal["lora_strength"]
    # null means "without the LoRA", so "No LoRA | 0.4 | 0.8" is one comparison.
    values: list[LoraStrength | None] = Field(min_length=MIN_CELLS, max_length=MAX_CELLS)


class SeedAxis(ApiRequest):
    kind: Literal["seed"]
    values: list[Seed] = Field(min_length=MIN_CELLS, max_length=MAX_CELLS)


class ModelAxis(ApiRequest):
    kind: Literal["model"]
    values: list[int] = Field(min_length=MIN_CELLS, max_length=MAX_CELLS)


CompareAxis = Annotated[LoraStrengthAxis | SeedAxis | ModelAxis, Field(discriminator="kind")]


class CompareRequest(ApiRequest):
    """Shared settings for every cell, plus the one setting that varies (`axis`).

    The setting named by the axis must not also be given as a shared value, so a request can
    never be ambiguous about which value a cell uses.
    """

    axis: CompareAxis
    prompt: str = Field(min_length=1, max_length=2000)
    negative_prompt: NegativePrompt = ""
    model_id: int | None = None
    lora_id: int | None = None
    lora_strength: LoraStrength = 1.0
    width: ImageSize = 512
    height: ImageSize = 512
    steps: Steps = 25
    guidance_scale: GuidanceScale = 7.5
    # Shared by all cells so only the axis differs; picked at random when omitted.
    seed: Seed | None = None

    @model_validator(mode="after")
    def _check_axis_consistency(self) -> "CompareRequest":
        values = self.axis.values
        if len(set(values)) != len(values):
            raise ValueError("Comparison values must be unique.")
        kind = self.axis.kind
        if kind == "model" and self.model_id is not None:
            raise ValueError("Leave model_id empty when comparing models.")
        if kind != "model" and self.model_id is None:
            raise ValueError("model_id is required.")
        if kind == "seed" and self.seed is not None:
            raise ValueError("Leave seed empty when comparing seeds.")
        if kind == "lora_strength" and self.lora_id is None:
            raise ValueError("Choose a LoRA to compare its strengths.")
        return self


class ComparisonSummary(ApiModel):
    id: int
    created_at: UtcDatetime
    prompt: str
    axis: str
    axis_values: list[float | int | None]
    status: str
    error_message: str | None


class ComparisonOut(ComparisonSummary):
    # Cells that were produced, in order; `comparison_index` maps each to `axis_values`.
    cells: list[GenerationOut]
