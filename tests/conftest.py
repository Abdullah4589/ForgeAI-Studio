from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from forge_api.config import Settings
from forge_api.main import create_app
from tests.helpers import write_diffusers_model


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    models = tmp_path / "models"
    write_diffusers_model(models, "tiny-sd", "StableDiffusionPipeline")
    return Settings(
        database_url=f"sqlite:///{(tmp_path / 'test.db').as_posix()}",
        model_directory=models,
        lora_directory=tmp_path / "loras",
        output_directory=tmp_path / "outputs",
        generation_backend="mock",
        mock_step_delay_seconds=0,
        model_idle_unload_seconds=0,
        max_upload_size_mb=1,
        log_level="WARNING",
    )


@pytest.fixture
def client(settings: Settings) -> Iterator[TestClient]:
    with TestClient(create_app(settings)) as test_client:
        yield test_client
