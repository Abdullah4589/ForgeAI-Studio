"""Long-lived application services, created once at startup and shared via `app.state`."""

from dataclasses import dataclass
from typing import Literal

from sqlalchemy import Engine
from sqlalchemy.orm import Session, sessionmaker

from ai.generation.types import GenerationBackend
from ai.model_manager.manager import ModelManager
from forge_api.config import Settings
from forge_api.jobs.manager import JobManager


@dataclass
class AppServices:
    settings: Settings
    engine: Engine
    session_factory: sessionmaker[Session]
    model_manager: ModelManager
    backend: GenerationBackend
    jobs: JobManager
    device: Literal["cuda", "cpu"]
