import time
from typing import Any

from fastapi.testclient import TestClient
from PIL import Image

from forge_api.config import Settings
from forge_api.db.models import DatasetImage
from forge_api.main import create_app
from tests.helpers import encode, picture
from tests.integration.test_api import model_id, wait_for_job


def dataset_with_images(client: TestClient, count: int) -> tuple[int, list[int]]:
    dataset = client.post("/api/datasets", json={"name": "Captions"}).json()
    files = [("files", (f"{i}.png", encode(picture(i)), "image/png")) for i in range(count)]
    added = client.post(f"/api/datasets/{dataset['id']}/images", files=files).json()["added"]
    return dataset["id"], [image["id"] for image in added]


def caption(client: TestClient, dataset_id: int, **body: Any) -> dict[str, Any]:
    response = client.post(f"/api/datasets/{dataset_id}/captions", json=body)
    assert response.status_code == 202, response.text
    created: dict[str, Any] = response.json()
    job = wait_for_job(client, created["id"])
    assert job["status"] == "completed", job
    return created


def images_by_id(client: TestClient, dataset_id: int) -> dict[int, dict[str, Any]]:
    images = client.get(f"/api/datasets/{dataset_id}").json()["images"]
    return {image["id"]: image for image in images}


def set_caption(client: TestClient, dataset_id: int, image_id: int, text: str) -> None:
    response = client.patch(f"/api/datasets/{dataset_id}/images/{image_id}", json={"caption": text})
    assert response.status_code == 200


def test_captions_every_uncaptioned_image(client: TestClient) -> None:
    dataset_id, _ = dataset_with_images(client, 3)
    created = caption(client, dataset_id)
    assert (created["queued"], created["skipped_manual"], created["skipped_existing"]) == (3, 0, 0)
    assert created["kind"] == "captioning"

    for image in images_by_id(client, dataset_id).values():
        assert image["caption"].startswith("a mock caption of a 512x512")  # framing removed
        assert image["caption_source"] == "ai"
        assert image["caption_model"] == "mock"
        assert image["caption_updated_at"] is not None
    assert client.get(f"/api/datasets/{dataset_id}").json()["uncaptioned_count"] == 0


def test_manual_captions_are_protected_unless_confirmed(client: TestClient) -> None:
    dataset_id, ids = dataset_with_images(client, 3)
    set_caption(client, dataset_id, ids[0], "my own words")
    caption(client, dataset_id, image_ids=[ids[1]])  # ids[1] becomes an AI caption

    # Default: only the empty one.
    created = caption(client, dataset_id)
    assert (created["queued"], created["skipped_manual"], created["skipped_existing"]) == (1, 1, 1)
    assert images_by_id(client, dataset_id)[ids[0]]["caption"] == "my own words"

    # replace_ai: refreshes AI captions but still leaves the manual one alone.
    created = caption(client, dataset_id, overwrite="replace_ai")
    assert (created["queued"], created["skipped_manual"]) == (2, 1)
    assert images_by_id(client, dataset_id)[ids[0]]["caption"] == "my own words"

    # everything: the explicit, confirmed overwrite.
    caption(client, dataset_id, overwrite="everything", image_ids=[ids[0]])
    overwritten = images_by_id(client, dataset_id)[ids[0]]
    assert overwritten["caption_source"] == "ai"
    assert overwritten["caption"].startswith("a mock caption")


def test_editing_an_ai_caption_makes_it_manual(client: TestClient) -> None:
    dataset_id, ids = dataset_with_images(client, 1)
    caption(client, dataset_id)
    set_caption(client, dataset_id, ids[0], "a better description")
    image = images_by_id(client, dataset_id)[ids[0]]
    assert (image["caption_source"], image["caption_model"]) == ("manual", None)

    response = client.post(f"/api/datasets/{dataset_id}/captions", json={"overwrite": "replace_ai"})
    assert response.status_code == 422
    assert response.json()["error"]["message"] == "No images need captions with these settings."


def test_request_validation(client: TestClient) -> None:
    dataset_id, _ = dataset_with_images(client, 1)
    _, other_ids = dataset_with_images(client, 1)
    foreign = client.post(f"/api/datasets/{dataset_id}/captions", json={"image_ids": other_ids})
    assert foreign.status_code == 422
    bad_mode = client.post(f"/api/datasets/{dataset_id}/captions", json={"overwrite": "all"})
    assert bad_mode.status_code == 422
    assert client.post("/api/datasets/999/captions", json={}).status_code == 404


def test_generation_model_is_released_before_captioning(client: TestClient) -> None:
    services = client.app.state.services  # type: ignore[attr-defined]
    released: list[str] = []
    original = services.backend.release
    services.backend.release = lambda: released.append("backend") or original()
    dataset_id, _ = dataset_with_images(client, 1)
    caption(client, dataset_id)
    assert released == ["backend"]


def test_one_job_at_a_time_and_cancel_keeps_finished(settings: Settings) -> None:
    slow = settings.model_copy(
        update={"mock_caption_delay_seconds": 0.3, "mock_step_delay_seconds": 0.05}
    )
    with TestClient(create_app(slow)) as client:
        dataset_id, _ = dataset_with_images(client, 5)
        job = client.post(f"/api/datasets/{dataset_id}/captions", json={}).json()

        busy = client.post("/api/generate", json={"model_id": model_id(client), "prompt": "x"})
        assert busy.status_code == 409
        assert client.post(f"/api/datasets/{dataset_id}/captions", json={}).status_code == 409

        deadline = time.monotonic() + 10
        while client.get(f"/api/datasets/{dataset_id}").json()["uncaptioned_count"] == 5:
            assert time.monotonic() < deadline, "no caption was ever saved"
            time.sleep(0.02)
        client.post("/api/generate/cancel", json={"job_id": job["id"]})
        assert wait_for_job(client, job["id"])["status"] == "cancelled"

        captioned = [i for i in images_by_id(client, dataset_id).values() if i["caption"]]
        assert 1 <= len(captioned) < 5


def test_edit_during_run_is_not_overwritten(client: TestClient) -> None:
    """A caption typed by hand while the model is working on that image must win."""
    dataset_id, ids = dataset_with_images(client, 1)
    services = client.app.state.services  # type: ignore[attr-defined]

    class EditingCaptioner:
        name = "editing"

        def caption(self, image: Image.Image) -> str:
            with services.session_factory() as db:
                row = db.get(DatasetImage, ids[0])
                row.caption, row.caption_source = "typed meanwhile", "manual"
                db.commit()
            return "ai text"

        def release(self) -> None:
            return None

    services.captioner = EditingCaptioner()
    caption(client, dataset_id)
    image = images_by_id(client, dataset_id)[ids[0]]
    assert (image["caption"], image["caption_source"]) == ("typed meanwhile", "manual")


def test_unreadable_image_is_skipped_not_fatal(client: TestClient, settings: Settings) -> None:
    dataset_id, _ = dataset_with_images(client, 2)
    first = next(p for p in (settings.dataset_directory / str(dataset_id) / "images").iterdir())
    first.write_bytes(b"corrupted on disk")
    response = client.post(f"/api/datasets/{dataset_id}/captions", json={}).json()
    job = wait_for_job(client, response["id"])
    assert job["status"] == "completed"
    assert job["result"]["failed"] == 1
    assert job["result"]["captioned"] == 1


def test_settings_show_caption_config(client: TestClient) -> None:
    runtime = client.get("/api/settings").json()["runtime"]
    assert runtime["caption_backend"] == "mock"
    assert runtime["caption_model_directory"].endswith("florence-2-base")
