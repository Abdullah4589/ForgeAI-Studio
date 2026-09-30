"""Application configuration loaded from environment variables (and an optional .env file)."""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", protected_namespaces=())

    database_url: str = "sqlite:///./storage/forge.db"
    model_directory: Path = Path("./storage/models")
    lora_directory: Path = Path("./storage/loras")
    output_directory: Path = Path("./storage/outputs")
    dataset_directory: Path = Path("./storage/datasets")
    device: Literal["auto", "cuda", "cpu"] = "auto"
    generation_backend: Literal["diffusers", "mock"] = "diffusers"
    enable_cpu_offload: bool = False
    # Artificial per-step delay for the mock backend so progress/cancel are observable in e2e tests.
    mock_step_delay_seconds: float = Field(default=0.05, ge=0)
    # florence (real, Florence-2) | mock (deterministic captions for tests/CI only)
    caption_backend: Literal["florence", "mock"] = "florence"
    caption_model_directory: Path = Path("./storage/captioners/florence-2-base")
    # Per-image delay for the mock captioner so progress/cancel are observable in e2e tests.
    mock_caption_delay_seconds: float = Field(default=0.05, ge=0)
    # Unload the model after this many idle seconds so it doesn't hold memory indefinitely.
    model_idle_unload_seconds: int = Field(default=600, ge=0)
    log_level: str = "INFO"
    max_upload_size_mb: int = Field(default=1024, gt=0)
    # Per-file limit for dataset image uploads.
    max_image_upload_mb: int = Field(default=25, gt=0)
    cors_origins: str = "http://localhost:3000"

    @field_validator("log_level")
    @classmethod
    def _upper_log_level(cls, value: str) -> str:
        return value.upper()

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_size_mb * 1024 * 1024

    @property
    def max_image_upload_bytes(self) -> int:
        return self.max_image_upload_mb * 1024 * 1024

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    def ensure_directories(self) -> None:
        for directory in (
            self.model_directory,
            self.lora_directory,
            self.output_directory,
            self.dataset_directory,
        ):
            directory.mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    return Settings()
