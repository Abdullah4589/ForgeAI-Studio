from fastapi import APIRouter

from forge_api.dependencies import DbDep, ServicesDep
from forge_api.schemas.settings import GenerationDefaults, SettingsOut
from forge_api.schemas.system import SystemOut
from forge_api.services import settings_service, system_service

router = APIRouter(prefix="/api", tags=["system"])


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/system", response_model=SystemOut)
def system(services: ServicesDep) -> SystemOut:
    return system_service.system_status(services)


@router.get("/settings", response_model=SettingsOut)
def get_settings(db: DbDep, services: ServicesDep) -> SettingsOut:
    return SettingsOut(
        runtime=settings_service.runtime_config(services.settings, services.device),
        generation_defaults=settings_service.get_generation_defaults(db),
    )


@router.put("/settings/generation-defaults", response_model=GenerationDefaults)
def save_generation_defaults(body: GenerationDefaults, db: DbDep) -> GenerationDefaults:
    return settings_service.save_generation_defaults(db, body)
