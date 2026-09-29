"""User-editable application settings persisted in the `application_settings` table."""

from pydantic import ValidationError
from sqlalchemy.orm import Session

from forge_api.config import Settings
from forge_api.db.models import ApplicationSetting
from forge_api.schemas.settings import GenerationDefaults, RuntimeConfigOut

GENERATION_DEFAULTS_KEY = "generation_defaults"


def get_generation_defaults(db: Session) -> GenerationDefaults:
    row = db.get(ApplicationSetting, GENERATION_DEFAULTS_KEY)
    if row is None:
        return GenerationDefaults()
    try:
        return GenerationDefaults.model_validate(row.value)
    except ValidationError:
        # Stored values from an older schema shouldn't break the app; fall back to defaults.
        return GenerationDefaults()


def save_generation_defaults(db: Session, defaults: GenerationDefaults) -> GenerationDefaults:
    row = db.get(ApplicationSetting, GENERATION_DEFAULTS_KEY)
    if row is None:
        row = ApplicationSetting(key=GENERATION_DEFAULTS_KEY, value={})
        db.add(row)
    row.value = defaults.model_dump()
    db.commit()
    return defaults


def runtime_config(settings: Settings, device: str) -> RuntimeConfigOut:
    return RuntimeConfigOut(
        model_directory=str(settings.model_directory),
        lora_directory=str(settings.lora_directory),
        output_directory=str(settings.output_directory),
        dataset_directory=str(settings.dataset_directory),
        device=device,
        generation_backend=settings.generation_backend,
        enable_cpu_offload=settings.enable_cpu_offload,
        model_idle_unload_seconds=settings.model_idle_unload_seconds,
        max_upload_size_mb=settings.max_upload_size_mb,
    )
