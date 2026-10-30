import secrets
from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from forge_api.container import AppServices
from forge_api.errors import UnauthorizedError


def get_services(request: Request) -> AppServices:
    services: AppServices = request.app.state.services
    return services


def get_db(services: Annotated[AppServices, Depends(get_services)]) -> Iterator[Session]:
    with services.session_factory() as session:
        yield session


ServicesDep = Annotated[AppServices, Depends(get_services)]
DbDep = Annotated[Session, Depends(get_db)]

_optional_bearer = HTTPBearer(auto_error=False)


def require_api_token(
    services: ServicesDep,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_optional_bearer)],
) -> None:
    """Reject mutating requests when API_TOKEN is set and the bearer token does not match.

    An empty token leaves the API open, which is the local-development default. Reads are not
    wired to this dependency: the UI and the Docker health check stay usable without a secret.
    """
    expected = services.settings.api_token
    if not expected:
        return
    provided = credentials.credentials if credentials is not None else ""
    if not provided or not secrets.compare_digest(provided, expected):
        raise UnauthorizedError(
            "A valid API token is required. Send Authorization: Bearer <token>."
        )


require_mutation_auth = [Depends(require_api_token)]
