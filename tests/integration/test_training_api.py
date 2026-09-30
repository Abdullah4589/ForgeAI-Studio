import json
import time
from typing import Any

from fastapi.testclient import TestClient

from forge_api.config import Settings
from forge_api.db.models import TrainingJob
from forge_api.db.session import create_db_engine, create_session_factory
from forge_api.main import create_app
from tests.helpers import (
    SD15_LORA_TENSORS,
    encode,
    picture,
    write_diffusers_model,
    write_safetensors,
)
from tests.integration.test_api import model_id, wait_for_job


def dataset(client: TestClient, captions: list[str]) -> int:
    created = client.post("/api/datasets", json={"name": "Training set"}).json()
    files = [("files", (f"{i}.png", encode(picture(i)), "image/png")) for i in range(len(captions))]
    added = client.post(f"/api/datasets/{created['id']}/images", files=files).json()["added"]
    for image, caption in zip(added, captions, strict=True):
        if caption:
            client.patch(
                f"/api/datasets/{created['id']}/images/{image['id']}", json={"caption": caption}
            )
    dataset_id: int = created["id"]
    return dataset_id


def start(client: TestClient, **overrides: Any) -> Any:
    body = {
        "dataset_id": overrides.pop("dataset_id", None) or dataset(client, ["a red house", ""]),
        "base_model_id": model_id(client),
        "name": "my-style",
        "trigger_word": "fgx",
        "resolution": 256,
        "steps": 5,
        "save_every": 2,
        "sample_count": 2,
        **overrides,
    }
    return client.post("/api/training", json=body)


def run_to_end(client: TestClient, **overrides: Any) -> dict[str, Any]:
    response = start(client, **overrides)
    assert response.status_code == 202, response.text
    created = response.json()
    wait_for_job(client, created["id"])
    run: dict[str, Any] = client.get(f"/api/training/{created['run_id']}").json()
    return run


def test_training_produces_a_registered_lora(client: TestClient, settings: Settings) -> None:
    run = run_to_end(client)
    assert run["status"] == "completed", run
    assert (run["current_step"], run["steps"], run["image_count"]) == (5, 5, 2)
    assert [point[0] for point in run["loss_history"]] == [1, 2, 3, 4, 5]
    assert run["last_loss"] is not None and run["avg_step_seconds"] is not None
    assert run["has_checkpoint"] is True
    assert run["started_at"] and run["finished_at"]

    lora = next(x for x in client.get("/api/loras").json() if x["id"] == run["lora_id"])
    assert (lora["filename"], lora["base_architecture"], lora["trigger_words"]) == (
        "my-style.safetensors",
        "sd15",
        "fgx",
    )
    assert "2 images, 5 steps, 256 px" in lora["description"]
    assert (settings.lora_directory / "my-style.safetensors").is_file()

    assert len(run["sample_urls"]) == 2
    sample = client.get(run["sample_urls"][0])
    assert (sample.status_code, sample.headers["content-type"]) == (200, "image/png")

    # Each caption is prefixed with the trigger word; an uncaptioned image trains on it alone.
    config = json.loads((settings.training_directory / str(run["id"]) / "config.json").read_text())
    assert [item["caption"] for item in config["items"]] == ["fgx, a red house", "fgx"]


def test_trained_lora_can_be_used_for_generation(client: TestClient) -> None:
    run = run_to_end(client)
    response = client.post(
        "/api/generate",
        json={
            "model_id": model_id(client),
            "prompt": "fgx, a castle",
            "lora_id": run["lora_id"],
            "width": 256,
            "height": 256,
            "steps": 2,
        },
    )
    assert response.status_code == 202
    assert wait_for_job(client, response.json()["id"])["status"] == "completed"


def test_name_is_sanitised(client: TestClient) -> None:
    run = run_to_end(client, name="../../My Style v2")
    assert run["name"] == "My_Style_v2"


def test_validation(client: TestClient, settings: Settings, tmp_path: Any) -> None:
    empty = client.post("/api/datasets", json={"name": "Empty"}).json()["id"]
    assert start(client, dataset_id=empty).status_code == 422

    write_diffusers_model(settings.model_directory, "xl", "StableDiffusionXLPipeline")
    client.post("/api/models/rescan")
    sdxl = start(client, base_model_id=model_id(client, "xl"))
    assert sdxl.status_code == 422
    assert "Stable Diffusion 1.x" in sdxl.json()["error"]["message"]

    write_safetensors(settings.lora_directory / "taken.safetensors", SD15_LORA_TENSORS)
    assert start(client, name="taken").status_code == 409

    for bad in (
        {"resolution": 300},
        {"rank": 0},
        {"learning_rate": 1},
        {"steps": 0},
        {"sample_count": 9},
        {"name": ""},
    ):
        assert start(client, **bad).status_code == 422, bad
    assert client.get("/api/training").json() == []


def test_failure_is_recorded(client: TestClient) -> None:
    run = run_to_end(client, name="mock-fail")
    assert run["status"] == "failed"
    assert run["error_message"] == "Mock training failed on purpose."
    assert run["lora_id"] is None
    assert not any(
        x["filename"] == "mock-fail.safetensors" for x in client.get("/api/loras").json()
    )


def test_cancel_keeps_checkpoint_and_blocks_other_jobs(settings: Settings) -> None:
    slow = settings.model_copy(update={"mock_training_step_delay_seconds": 0.05})
    with TestClient(create_app(slow)) as client:
        created = start(client, steps=400, save_every=5).json()

        busy = client.post("/api/generate", json={"model_id": model_id(client), "prompt": "x"})
        assert busy.status_code == 409
        assert "training" in busy.json()["error"]["message"]

        deadline = time.monotonic() + 20
        while client.get(f"/api/training/{created['run_id']}").json()["current_step"] < 12:
            assert time.monotonic() < deadline, "training never progressed"
            time.sleep(0.05)
        assert client.delete(f"/api/training/{created['run_id']}").status_code == 409
        client.post("/api/generate/cancel", json={"job_id": created["id"]})
        assert wait_for_job(client, created["id"], timeout=30)["status"] == "cancelled"

        run = client.get(f"/api/training/{created['run_id']}").json()
        assert run["status"] == "cancelled"
        assert run["has_checkpoint"] is True
        assert run["lora_id"] is None


def test_models_are_released_before_training(client: TestClient) -> None:
    services = client.app.state.services  # type: ignore[attr-defined]
    released: list[str] = []
    services.backend.release = lambda: released.append("backend")
    services.captioner.release = lambda: released.append("captioner")
    run_to_end(client)
    assert released == ["backend", "captioner"]


def test_delete_run_keeps_lora(client: TestClient, settings: Settings) -> None:
    run = run_to_end(client)
    folder = settings.training_directory / str(run["id"])
    assert folder.is_dir()
    assert client.delete(f"/api/training/{run['id']}").status_code == 204
    assert not folder.exists()
    assert client.get(f"/api/training/{run['id']}").status_code == 404
    assert any(x["id"] == run["lora_id"] for x in client.get("/api/loras").json())


def test_runs_are_listed_newest_first(client: TestClient) -> None:
    first = run_to_end(client, name="first")
    second = run_to_end(client, name="second")
    assert [r["id"] for r in client.get("/api/training").json()] == [second["id"], first["id"]]


def test_unfinished_runs_are_marked_interrupted_on_startup(settings: Settings) -> None:
    with TestClient(create_app(settings)):
        pass  # runs migrations
    engine = create_db_engine(settings.database_url)
    with create_session_factory(engine)() as db:
        db.add(
            TrainingJob(
                name="x",
                dataset_name="d",
                base_model_name="m",
                resolution=256,
                rank=4,
                alpha=4,
                learning_rate=1e-4,
                batch_size=1,
                steps=10,
                save_every=0,
                seed=1,
                sample_count=0,
                sample_steps=5,
                image_count=1,
                status="running",
            )
        )
        db.commit()
    engine.dispose()
    with TestClient(create_app(settings)) as client:
        (run,) = client.get("/api/training").json()
        assert run["status"] == "interrupted"
        assert "stopped" in run["error_message"]


def test_missing_sample_is_404(client: TestClient) -> None:
    run = run_to_end(client, sample_count=0)
    assert client.get(f"/api/training/{run['id']}/samples/0").status_code == 404
