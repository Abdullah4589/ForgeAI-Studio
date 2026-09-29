import time
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from forge_api.config import Settings
from forge_api.db.models import Comparison
from forge_api.db.session import create_db_engine, create_session_factory
from forge_api.main import create_app
from tests.helpers import SD15_LORA_TENSORS, write_diffusers_model, write_safetensors
from tests.integration.test_api import import_lora, model_id, wait_for_job

BASE = {"prompt": "a fox in the snow", "width": 256, "height": 256, "steps": 3}


def compare(client: TestClient, axis: dict[str, Any], **overrides: Any) -> Any:
    return client.post("/api/compare", json={**BASE, "axis": axis, **overrides})


def run(client: TestClient, axis: dict[str, Any], **overrides: Any) -> dict[str, Any]:
    response = compare(client, axis, **overrides)
    assert response.status_code == 202, response.text
    created = response.json()
    job = wait_for_job(client, created["id"])
    assert job["status"] == "completed", job
    assert job["result"]["comparison_id"] == created["comparison_id"]
    comparison: dict[str, Any] = client.get(f"/api/comparisons/{created['comparison_id']}").json()
    return comparison


def test_compare_lora_strengths_with_baseline(client: TestClient, tmp_path: Path) -> None:
    lora = import_lora(client, write_safetensors(tmp_path / "s.safetensors", SD15_LORA_TENSORS))
    lora_id = lora.json()["id"]
    comparison = run(
        client,
        {"kind": "lora_strength", "values": [None, 0.4, 0.8]},
        model_id=model_id(client),
        lora_id=lora_id,
        seed=42,
    )

    assert comparison["status"] == "completed"
    assert comparison["axis"] == "lora_strength"
    assert comparison["axis_values"] == [None, 0.4, 0.8]
    cells = comparison["cells"]
    assert [c["comparison_index"] for c in cells] == [0, 1, 2]
    assert [(c["lora_id"], c["lora_strength"]) for c in cells] == [
        (None, None),
        (lora_id, 0.4),
        (lora_id, 0.8),
    ]
    assert {c["seed"] for c in cells} == {42}
    assert all(len(c["images"]) == 1 for c in cells)
    # Every cell is also a normal history entry.
    assert client.get("/api/history").json()["total"] == 3


def test_compare_seeds(client: TestClient) -> None:
    comparison = run(client, {"kind": "seed", "values": [0, 1, 2]}, model_id=model_id(client))
    assert [c["seed"] for c in comparison["cells"]] == [0, 1, 2]
    urls = [c["images"][0]["url"] for c in comparison["cells"]]
    # Different seeds really produce different images.
    assert len({client.get(u).content for u in urls}) == 3


def test_compare_models(client: TestClient, settings: Settings) -> None:
    write_diffusers_model(settings.model_directory, "other-sd", "StableDiffusionPipeline")
    client.post("/api/models/rescan")
    ids = [model_id(client), model_id(client, "other sd")]
    comparison = run(client, {"kind": "model", "values": ids}, seed=5)
    assert [c["model_name"] for c in comparison["cells"]] == ["tiny sd", "other sd"]


def test_invalid_cell_is_rejected_before_anything_runs(
    client: TestClient, settings: Settings, tmp_path: Path
) -> None:
    write_diffusers_model(settings.model_directory, "xl", "StableDiffusionXLPipeline")
    client.post("/api/models/rescan")
    lora_id = import_lora(
        client, write_safetensors(tmp_path / "s.safetensors", SD15_LORA_TENSORS)
    ).json()["id"]

    # The SD 1.x LoRA is fine for one model but not for the SDXL one.
    response = compare(
        client,
        {"kind": "model", "values": [model_id(client), model_id(client, "xl")]},
        lora_id=lora_id,
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "incompatible_lora"
    assert client.get("/api/comparisons").json() == []
    assert client.get("/api/history").json()["total"] == 0


def test_request_validation_errors(client: TestClient) -> None:
    response = compare(client, {"kind": "seed", "values": [1, 1]}, model_id=model_id(client))
    assert response.status_code == 422
    assert "unique" in response.json()["error"]["fields"][0]["message"]

    missing = compare(client, {"kind": "model", "values": [999, 998]})
    assert missing.status_code == 404


def test_cancel_keeps_completed_cells(settings: Settings) -> None:
    slow = settings.model_copy(update={"mock_step_delay_seconds": 0.05})
    with TestClient(create_app(slow)) as client:
        body = {**BASE, "steps": 10, "model_id": model_id(client)}
        job = client.post(
            "/api/compare", json={**body, "axis": {"kind": "seed", "values": [1, 2, 3]}}
        )
        job_id = job.json()["id"]

        # A second job of any kind is refused while the comparison runs.
        busy = client.post("/api/generate", json={**BASE, "model_id": model_id(client)})
        assert busy.status_code == 409

        # Wait until the first cell is saved, then cancel.
        deadline = time.monotonic() + 10
        while client.get("/api/history").json()["total"] < 1:
            assert time.monotonic() < deadline, "first cell was never saved"
            time.sleep(0.02)
        client.post("/api/generate/cancel", json={"job_id": job_id})
        assert wait_for_job(client, job_id)["status"] == "cancelled"

        (summary,) = client.get("/api/comparisons").json()
        assert summary["status"] == "cancelled"
        cells = client.get(f"/api/comparisons/{summary['id']}").json()["cells"]
        assert 1 <= len(cells) < 3
        assert cells[0]["seed"] == 1


def test_delete_comparison_removes_cells(client: TestClient, settings: Settings) -> None:
    comparison = run(client, {"kind": "seed", "values": [1, 2]}, model_id=model_id(client))
    assert len(list(settings.output_directory.rglob("*.png"))) == 2

    assert client.delete(f"/api/comparisons/{comparison['id']}").status_code == 204
    assert client.get(f"/api/comparisons/{comparison['id']}").status_code == 404
    assert client.get("/api/history").json()["total"] == 0
    assert list(settings.output_directory.rglob("*.png")) == []


def test_list_comparisons_newest_first(client: TestClient) -> None:
    first = run(client, {"kind": "seed", "values": [1, 2]}, model_id=model_id(client))
    second = run(client, {"kind": "seed", "values": [3, 4]}, model_id=model_id(client))
    summaries = client.get("/api/comparisons").json()
    assert [s["id"] for s in summaries] == [second["id"], first["id"]]
    assert "cells" not in summaries[0]


def test_running_comparisons_are_marked_interrupted_on_startup(settings: Settings) -> None:
    with TestClient(create_app(settings)):
        pass  # runs migrations
    engine = create_db_engine(settings.database_url)
    with create_session_factory(engine)() as db:
        db.add(Comparison(prompt="x", axis="seed", axis_values=[1, 2]))
        db.commit()
    engine.dispose()

    with TestClient(create_app(settings)) as client:
        (summary,) = client.get("/api/comparisons").json()
        assert summary["status"] == "interrupted"
