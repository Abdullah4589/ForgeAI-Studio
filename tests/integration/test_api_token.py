"""API_TOKEN gates mutating routes and leaves reads open."""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from httpx import Response

from forge_api.config import Settings
from forge_api.main import create_app

TOKEN = "test-token"
AUTH = {"Authorization": f"Bearer {TOKEN}"}

# Every mutating route. Bodies only need to be JSON; auth runs before schema validation.
MUTATIONS: list[tuple[str, str, dict[str, object] | None]] = [
    ("POST", "/api/models/rescan", None),
    ("POST", "/api/models/load", {"model_id": 1}),
    ("POST", "/api/models/unload", None),
    ("POST", "/api/loras/rescan", None),
    ("PATCH", "/api/loras/1", {"enabled": False}),
    ("DELETE", "/api/loras/1", None),
    ("POST", "/api/generate", {"model_id": 1, "prompt": "x", "width": 256, "height": 256}),
    ("POST", "/api/generate/cancel", {"job_id": "missing"}),
    ("DELETE", "/api/history/1", None),
    ("DELETE", "/api/history/images/1", None),
    ("POST", "/api/compare", {"prompt": "x"}),
    ("DELETE", "/api/comparisons/1", None),
    ("POST", "/api/datasets", {"name": "set"}),
    ("PATCH", "/api/datasets/1", {"name": "renamed"}),
    ("DELETE", "/api/datasets/1", None),
    ("PUT", "/api/datasets/1/order", {"image_ids": []}),
    ("PATCH", "/api/datasets/1/images/1", {"caption": "a"}),
    ("DELETE", "/api/datasets/1/images/1", None),
    ("POST", "/api/datasets/1/captions", {}),
    ("PUT", "/api/settings/generation-defaults", {}),
    ("POST", "/api/training", {"name": "run", "dataset_id": 1, "base_model_id": 1}),
    ("DELETE", "/api/training/1", None),
]


@pytest.fixture
def secured_client(settings: Settings) -> Iterator[TestClient]:
    secured = settings.model_copy(update={"api_token": TOKEN})
    with TestClient(create_app(secured)) as client:
        yield client


def _call(
    client: TestClient,
    method: str,
    path: str,
    body: dict[str, object] | None,
    headers: dict[str, str] | None = None,
) -> Response:
    if body is None:
        return client.request(method, path, headers=headers)
    return client.request(method, path, json=body, headers=headers)


@pytest.mark.parametrize(("method", "path", "body"), MUTATIONS)
def test_mutating_routes_require_the_bearer_token(
    secured_client: TestClient, method: str, path: str, body: dict[str, object] | None
) -> None:
    denied = _call(secured_client, method, path, body)
    assert denied.status_code == 401, denied.text
    assert denied.json()["error"]["code"] == "unauthorized"
    wrong = _call(secured_client, method, path, body, {"Authorization": "Bearer nope"})
    assert wrong.status_code == 401


def test_reads_and_a_matching_token_are_allowed(secured_client: TestClient) -> None:
    assert secured_client.get("/api/health").status_code == 200
    assert secured_client.get("/api/models").status_code == 200
    assert secured_client.get("/api/settings").status_code == 200
    assert secured_client.get("/api/jobs/missing").status_code == 404
    # A query parameter is not a substitute for the header.
    assert secured_client.post(f"/api/models/rescan?token={TOKEN}").status_code == 401
    assert (
        secured_client.post(
            "/api/models/rescan", headers={"Authorization": "Basic dGVzdA=="}
        ).status_code
        == 401
    )

    rescanned = secured_client.post("/api/models/rescan", headers=AUTH)
    assert rescanned.status_code == 200, rescanned.text
    generated = secured_client.post(
        "/api/generate",
        headers=AUTH,
        json={"model_id": rescanned.json()[0]["id"], "prompt": "fox", "width": 256, "height": 256},
    )
    assert generated.status_code == 202, generated.text


def test_uploads_require_the_token(secured_client: TestClient) -> None:
    lora = secured_client.post(
        "/api/loras/import",
        files={"file": ("a.safetensors", b"nope", "application/octet-stream")},
    )
    images = secured_client.post(
        "/api/datasets/1/images",
        files=[("files", ("a.png", b"nope", "image/png"))],
    )
    assert lora.status_code == 401
    assert images.status_code == 401
