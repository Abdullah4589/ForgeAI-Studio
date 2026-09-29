import json
import time
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from forge_api.config import Settings
from forge_api.main import create_app
from tests.helpers import (
    SD15_LORA_TENSORS,
    SDXL_LORA_TENSORS,
    write_diffusers_model,
    write_safetensors,
)


def model_id(client: TestClient, name: str = "tiny sd") -> int:
    models = client.get("/api/models").json()
    return next(m["id"] for m in models if m["name"] == name)


def wait_for_job(client: TestClient, job_id: str, timeout: float = 10.0) -> dict[str, Any]:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        job: dict[str, Any] = client.get(f"/api/jobs/{job_id}").json()
        if job["status"] in ("completed", "failed", "cancelled"):
            return job
        time.sleep(0.02)
    raise AssertionError("job did not finish")


def generate(client: TestClient, **overrides: Any) -> dict[str, Any]:
    body = {"model_id": model_id(client), "prompt": "a red fox", "width": 256, "height": 256}
    body.update(overrides)
    response = client.post("/api/generate", json=body)
    assert response.status_code == 202, response.text
    return wait_for_job(client, response.json()["id"])


def import_lora(client: TestClient, path: Path, filename: str | None = None) -> Any:
    with path.open("rb") as handle:
        return client.post(
            "/api/loras/import",
            files={"file": (filename or path.name, handle, "application/octet-stream")},
        )


# ---- system ---------------------------------------------------------------------------


def test_health_and_system(client: TestClient) -> None:
    assert client.get("/api/health").json() == {"status": "ok"}
    system = client.get("/api/system").json()
    assert system["generation_backend"] == "mock"
    assert system["ram_total_bytes"] > 0
    assert system["disk_total_bytes"] > 0
    assert isinstance(system["cuda_available"], bool)


def test_settings_roundtrip(client: TestClient) -> None:
    settings = client.get("/api/settings").json()
    assert settings["runtime"]["generation_backend"] == "mock"
    assert settings["generation_defaults"]["width"] == 512

    new_defaults = {**settings["generation_defaults"], "steps": 12, "negative_prompt": "blurry"}
    assert client.put("/api/settings/generation-defaults", json=new_defaults).status_code == 200
    assert client.get("/api/settings").json()["generation_defaults"]["steps"] == 12

    bad = client.put("/api/settings/generation-defaults", json={**new_defaults, "width": 100})
    assert bad.status_code == 422


# ---- models ---------------------------------------------------------------------------


def test_models_are_discovered_and_rescanned(client: TestClient, settings: Settings) -> None:
    models = client.get("/api/models").json()
    assert [m["name"] for m in models] == ["tiny sd"]
    assert models[0]["architecture"] == "sd15"
    assert models[0]["loaded"] is False

    write_diffusers_model(settings.model_directory, "xl", "StableDiffusionXLPipeline")
    rescanned = client.post("/api/models/rescan").json()
    assert {m["name"]: m["architecture"] for m in rescanned} == {"tiny sd": "sd15", "xl": "sdxl"}


def test_removed_model_is_marked_unavailable(client: TestClient, settings: Settings) -> None:
    (settings.model_directory / "tiny-sd" / "model_index.json").unlink()
    (models,) = [client.post("/api/models/rescan").json()]
    assert models[0]["available"] is False
    response = client.post("/api/generate", json={"model_id": models[0]["id"], "prompt": "x"})
    assert response.status_code == 422


def test_load_is_rejected_in_mock_mode(client: TestClient) -> None:
    response = client.post("/api/models/load", json={"model_id": model_id(client)})
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "conflict"


# ---- generation -----------------------------------------------------------------------


def test_generation_end_to_end(client: TestClient, settings: Settings) -> None:
    job = generate(client, num_images=2, seed=1234, negative_prompt="blurry", steps=4)
    assert job["status"] == "completed", job
    assert (job["step"], job["total_steps"]) == (4, 4)

    generation = client.get(f"/api/history/{job['result']['generation_id']}").json()
    assert generation["prompt"] == "a red fox"
    assert generation["negative_prompt"] == "blurry"
    assert generation["model_name"] == "tiny sd"
    assert generation["seed"] == 1234
    assert (generation["width"], generation["height"], generation["steps"]) == (256, 256, 4)
    assert generation["duration_ms"] >= 0
    assert generation["pipeline_config"] == {"backend": "mock"}
    assert [img["seed"] for img in generation["images"]] == [1234, 1235]

    image = client.get(generation["images"][0]["url"])
    assert image.status_code == 200
    assert image.headers["content-type"] == "image/png"
    assert image.content[:8] == b"\x89PNG\r\n\x1a\n"

    download = client.get(generation["images"][0]["url"], params={"download": "true"})
    assert "attachment" in download.headers["content-disposition"]
    assert len(list(settings.output_directory.rglob("*.png"))) == 2


def test_random_seed_is_stored(client: TestClient) -> None:
    job = generate(client)
    generation = client.get(f"/api/history/{job['result']['generation_id']}").json()
    assert 0 <= generation["seed"] < 2**32


def test_same_seed_reproduces_same_image(client: TestClient) -> None:
    first = generate(client, seed=99)["result"]["generation_id"]
    second = generate(client, seed=99)["result"]["generation_id"]
    urls = [client.get(f"/api/history/{g}").json()["images"][0]["url"] for g in (first, second)]
    assert client.get(urls[0]).content == client.get(urls[1]).content


def test_validation_errors_are_field_level(client: TestClient) -> None:
    response = client.post(
        "/api/generate", json={"model_id": model_id(client), "prompt": "", "width": 500}
    )
    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "validation_error"
    assert {f["field"] for f in error["fields"]} == {"prompt", "width"}


def test_unknown_model_is_404(client: TestClient) -> None:
    response = client.post("/api/generate", json={"model_id": 999, "prompt": "x"})
    assert response.status_code == 404
    assert response.json()["error"]["message"] == "Model not found."


def test_unsupported_architecture_is_rejected(client: TestClient, settings: Settings) -> None:
    write_diffusers_model(settings.model_directory, "flux", "FluxPipeline")
    client.post("/api/models/rescan")
    response = client.post(
        "/api/generate", json={"model_id": model_id(client, "flux"), "prompt": "x"}
    )
    assert response.status_code == 422


def test_sse_stream_ends_with_terminal_event(client: TestClient) -> None:
    job = client.post(
        "/api/generate",
        json={"model_id": model_id(client), "prompt": "fox", "width": 256, "height": 256},
    ).json()
    events = []
    with client.stream("GET", f"/api/jobs/{job['id']}/events") as stream:
        for line in stream.iter_lines():
            if line.startswith("data: "):
                events.append(json.loads(line.removeprefix("data: ")))
    assert events[-1]["status"] == "completed"
    assert events[-1]["result"]["generation_id"] > 0


def test_unknown_job_is_404(client: TestClient) -> None:
    assert client.get("/api/jobs/nope").status_code == 404
    assert client.get("/api/jobs/nope/events").status_code == 404
    assert client.post("/api/generate/cancel", json={"job_id": "nope"}).status_code == 404


def test_cancel_and_single_active_generation(settings: Settings) -> None:
    slow = settings.model_copy(update={"mock_step_delay_seconds": 0.05})
    with TestClient(create_app(slow)) as client:
        body = {
            "model_id": model_id(client),
            "prompt": "slow",
            "steps": 100,
            "width": 256,
            "height": 256,
        }
        job = client.post("/api/generate", json=body).json()

        busy = client.post("/api/generate", json=body)
        assert busy.status_code == 409

        assert client.post("/api/generate/cancel", json={"job_id": job["id"]}).status_code == 200
        assert wait_for_job(client, job["id"])["status"] == "cancelled"
        assert client.get("/api/history").json()["total"] == 0


# ---- LoRAs ----------------------------------------------------------------------------


def test_lora_import_update_and_delete(
    client: TestClient, settings: Settings, tmp_path: Path
) -> None:
    source = write_safetensors(tmp_path / "upload.safetensors", SD15_LORA_TENSORS)
    response = import_lora(client, source, "../../My Style.safetensors")
    assert response.status_code == 201, response.text
    lora = response.json()
    assert lora["filename"] == "My_Style.safetensors"
    assert lora["base_architecture"] == "sd15"
    assert (settings.lora_directory / "My_Style.safetensors").is_file()

    duplicate = import_lora(client, source, "My Style.safetensors")
    assert duplicate.status_code == 409

    patched = client.patch(
        f"/api/loras/{lora['id']}",
        json={"trigger_words": "mystyle", "description": "Test", "default_strength": 0.6},
    ).json()
    assert (patched["trigger_words"], patched["default_strength"]) == ("mystyle", 0.6)
    assert client.patch(f"/api/loras/{lora['id']}", json={"enabled": None}).status_code == 422

    assert client.delete(f"/api/loras/{lora['id']}").status_code == 204
    assert not (settings.lora_directory / "My_Style.safetensors").exists()
    assert client.get("/api/loras").json() == []


@pytest.mark.parametrize(
    ("filename", "content", "status"),
    [
        ("evil.ckpt", b"anything", 422),
        ("fake.safetensors", b"not really safetensors", 422),
        ("big.safetensors", b"x" * (1024 * 1024 + 1), 413),
    ],
    ids=["wrong-extension", "not-safetensors", "too-large"],
)
def test_lora_import_rejects_bad_files(
    client: TestClient,
    settings: Settings,
    tmp_path: Path,
    filename: str,
    content: bytes,
    status: int,
) -> None:
    path = tmp_path / "upload.bin"
    path.write_bytes(content)
    assert import_lora(client, path, filename).status_code == status
    # Nothing (not even a partial temp file) may be left behind.
    assert list(settings.lora_directory.iterdir()) == []


def test_generation_with_lora_is_recorded(client: TestClient, tmp_path: Path) -> None:
    lora = import_lora(
        client, write_safetensors(tmp_path / "s.safetensors", SD15_LORA_TENSORS)
    ).json()
    job = generate(client, lora_id=lora["id"], lora_strength=0.4)
    generation = client.get(f"/api/history/{job['result']['generation_id']}").json()
    assert (generation["lora_id"], generation["lora_name"], generation["lora_strength"]) == (
        lora["id"],
        "s",
        0.4,
    )


def test_incompatible_or_disabled_lora_is_rejected(client: TestClient, tmp_path: Path) -> None:
    xl = import_lora(
        client, write_safetensors(tmp_path / "xl.safetensors", SDXL_LORA_TENSORS)
    ).json()
    body = {"model_id": model_id(client), "prompt": "x", "lora_id": xl["id"]}
    response = client.post("/api/generate", json=body)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "incompatible_lora"

    sd = import_lora(
        client, write_safetensors(tmp_path / "sd.safetensors", SD15_LORA_TENSORS)
    ).json()
    client.patch(f"/api/loras/{sd['id']}", json={"enabled": False})
    response = client.post("/api/generate", json={**body, "lora_id": sd["id"]})
    assert response.status_code == 422
    assert "disabled" in response.json()["error"]["message"]


def test_loras_in_directory_are_discovered(client: TestClient, settings: Settings) -> None:
    write_safetensors(settings.lora_directory / "dropped.safetensors", SDXL_LORA_TENSORS)
    (settings.lora_directory / "junk.safetensors").write_bytes(b"junk")
    loras = client.post("/api/loras/rescan").json()
    assert [(lo["name"], lo["base_architecture"]) for lo in loras] == [("dropped", "sdxl")]


# ---- history --------------------------------------------------------------------------


def test_history_search_filter_sort_and_delete(
    client: TestClient, settings: Settings, tmp_path: Path
) -> None:
    lora = import_lora(
        client, write_safetensors(tmp_path / "s.safetensors", SD15_LORA_TENSORS)
    ).json()
    first = generate(client, prompt="a castle at dawn")["result"]["generation_id"]
    second = generate(client, prompt="100% sunny_beach", lora_id=lora["id"])["result"][
        "generation_id"
    ]

    newest = client.get("/api/history").json()
    assert newest["total"] == 2
    assert [g["id"] for g in newest["items"]] == [second, first]
    oldest = client.get("/api/history", params={"sort": "oldest"}).json()
    assert [g["id"] for g in oldest["items"]] == [first, second]

    def ids(**params: Any) -> list[int]:
        return [g["id"] for g in client.get("/api/history", params=params).json()["items"]]

    assert ids(q="CASTLE") == [first]
    assert ids(q="100%") == [second]  # wildcard characters are matched literally
    assert ids(q="y_b") == [second]
    assert ids(q="%") == [second]
    assert ids(lora_id=lora["id"]) == [second]
    assert ids(model_id=model_id(client)) == [second, first]
    assert client.get("/api/history", params={"sort": "random"}).status_code == 422

    assert client.delete(f"/api/history/{first}").status_code == 204
    assert client.get(f"/api/history/{first}").status_code == 404
    assert len(list(settings.output_directory.rglob("*.png"))) == 1


def test_deleting_last_image_removes_generation(client: TestClient) -> None:
    generation_id = generate(client, num_images=2)["result"]["generation_id"]
    images = client.get(f"/api/history/{generation_id}").json()["images"]

    assert client.delete(f"/api/history/images/{images[0]['id']}").status_code == 204
    assert len(client.get(f"/api/history/{generation_id}").json()["images"]) == 1
    assert client.get(images[0]["url"]).status_code == 404

    client.delete(f"/api/history/images/{images[1]['id']}")
    assert client.get(f"/api/history/{generation_id}").status_code == 404


def test_history_survives_lora_deletion(client: TestClient, tmp_path: Path) -> None:
    lora = import_lora(
        client, write_safetensors(tmp_path / "s.safetensors", SD15_LORA_TENSORS)
    ).json()
    generation_id = generate(client, lora_id=lora["id"])["result"]["generation_id"]
    client.delete(f"/api/loras/{lora['id']}")
    generation = client.get(f"/api/history/{generation_id}").json()
    assert generation["lora_id"] is None
    assert generation["lora_name"] == "s"
