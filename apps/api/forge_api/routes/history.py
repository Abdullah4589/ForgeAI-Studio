from typing import Annotated

from fastapi import APIRouter, Query, status

from forge_api.db.models import Generation
from forge_api.dependencies import DbDep, ServicesDep
from forge_api.schemas.history import GenerationOut, HistoryPage, SortOrder
from forge_api.services import history_service

router = APIRouter(prefix="/api/history", tags=["history"])


@router.get("", response_model=HistoryPage)
def list_history(
    db: DbDep,
    q: Annotated[str | None, Query(max_length=200)] = None,
    model_id: int | None = None,
    lora_id: int | None = None,
    sort: SortOrder = "newest",
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 24,
) -> HistoryPage:
    items, total = history_service.list_history(
        db,
        query=q.strip() if q else None,
        model_id=model_id,
        lora_id=lora_id,
        sort=sort,
        page=page,
        page_size=page_size,
    )
    return HistoryPage(
        items=[GenerationOut.model_validate(g) for g in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{generation_id}", response_model=GenerationOut)
def get_generation(generation_id: int, db: DbDep) -> Generation:
    return history_service.get_generation(db, generation_id)


@router.delete("/{generation_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_generation(generation_id: int, db: DbDep, services: ServicesDep) -> None:
    history_service.delete_generation(db, services.settings.output_directory, generation_id)


@router.delete("/images/{image_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_image(image_id: int, db: DbDep, services: ServicesDep) -> None:
    history_service.delete_image(db, services.settings.output_directory, image_id)
