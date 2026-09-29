from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from forge_api.container import AppServices


def get_services(request: Request) -> AppServices:
    services: AppServices = request.app.state.services
    return services


def get_db(services: Annotated[AppServices, Depends(get_services)]) -> Iterator[Session]:
    with services.session_factory() as session:
        yield session


ServicesDep = Annotated[AppServices, Depends(get_services)]
DbDep = Annotated[Session, Depends(get_db)]
