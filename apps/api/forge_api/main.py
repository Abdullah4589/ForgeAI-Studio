"""FastAPI application factory. Run with: uvicorn forge_api.main:app"""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from ai.captioning.factory import create_captioner
from ai.device import resolve_device
from ai.generation.factory import create_backend
from ai.model_manager.manager import ModelManager
from forge_api.config import Settings, get_settings
from forge_api.container import AppServices
from forge_api.db.session import create_db_engine, create_session_factory, run_migrations
from forge_api.errors import register_error_handlers
from forge_api.jobs.manager import JobManager
from forge_api.logging_config import configure_logging
from forge_api.routes import (
    captions,
    compare,
    datasets,
    generation,
    history,
    images,
    loras,
    models,
    system,
    training,
)
from forge_api.services.compare_service import mark_interrupted
from forge_api.services.lora_service import sync_loras
from forge_api.services.model_service import sync_models
from forge_api.services.training_service import mark_interrupted as mark_training_interrupted

logger = logging.getLogger(__name__)


def build_services(settings: Settings) -> AppServices:
    settings.ensure_directories()
    run_migrations(settings.database_url)
    engine = create_db_engine(settings.database_url)
    device = resolve_device(settings.device)
    model_manager = ModelManager()
    backend = create_backend(
        settings.generation_backend,
        model_manager=model_manager,
        device=device,
        enable_cpu_offload=settings.enable_cpu_offload,
        mock_step_delay_seconds=settings.mock_step_delay_seconds,
    )
    captioner = create_captioner(
        settings.caption_backend,
        model_dir=settings.caption_model_directory,
        device=device,
        mock_delay_seconds=settings.mock_caption_delay_seconds,
    )

    def release_models() -> None:
        backend.release()
        captioner.release()

    jobs = JobManager(idle_seconds=settings.model_idle_unload_seconds, on_idle=release_models)
    return AppServices(
        settings=settings,
        engine=engine,
        session_factory=create_session_factory(engine),
        model_manager=model_manager,
        backend=backend,
        captioner=captioner,
        jobs=jobs,
        device=device,
    )


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        configure_logging(settings.log_level)
        services = build_services(settings)
        with services.session_factory() as db:
            sync_models(db, settings.model_directory)
            sync_loras(db, settings.lora_directory)
            mark_interrupted(db)
            mark_training_interrupted(db)
        services.jobs.start()
        app.state.services = services
        logger.info(
            "app_started",
            extra={"device": services.device, "backend": settings.generation_backend},
        )
        try:
            yield
        finally:
            services.jobs.shutdown()
            services.backend.release()
            services.captioner.release()
            services.engine.dispose()

    app = FastAPI(title="ForgeAI Studio API", version="0.1.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["Content-Type"],
    )
    register_error_handlers(app)
    for module in (
        system,
        models,
        loras,
        generation,
        compare,
        history,
        images,
        datasets,
        captions,
        training,
    ):
        app.include_router(module.router)
    return app


app = create_app()
