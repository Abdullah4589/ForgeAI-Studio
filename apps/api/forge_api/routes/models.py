from fastapi import APIRouter

from forge_api.dependencies import DbDep, ServicesDep
from forge_api.schemas.models import ModelLoadRequest, ModelOut, ModelStatusOut
from forge_api.services import model_service

router = APIRouter(prefix="/api/models", tags=["models"])


@router.get("", response_model=list[ModelOut])
def list_models(db: DbDep, services: ServicesDep) -> list[ModelOut]:
    return model_service.list_models(db, services)


@router.post("/rescan", response_model=list[ModelOut])
def rescan_models(db: DbDep, services: ServicesDep) -> list[ModelOut]:
    model_service.sync_models(db, services.settings.model_directory)
    return model_service.list_models(db, services)


@router.post("/load", response_model=ModelStatusOut)
def load_model(body: ModelLoadRequest, db: DbDep, services: ServicesDep) -> ModelStatusOut:
    model_service.load_model(db, services, body.model_id)
    return ModelStatusOut(loaded_model_id=model_service.loaded_model_id(db, services))


@router.post("/unload", response_model=ModelStatusOut)
def unload_model(services: ServicesDep) -> ModelStatusOut:
    model_service.unload_model(services)
    return ModelStatusOut(loaded_model_id=None)
