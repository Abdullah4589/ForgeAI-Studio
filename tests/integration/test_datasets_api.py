import io
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from PIL import Image, ImageFilter

from forge_api.config import Settings
from forge_api.main import create_app
from tests.helpers import encode, picture

Upload = tuple[str, bytes]


def create(client: TestClient, **overrides: Any) -> dict[str, Any]:
    response = client.post("/api/datasets", json={"name": "Cats", **overrides})
    assert response.status_code == 201, response.text
    result: dict[str, Any] = response.json()
    return result


def upload(client: TestClient, dataset_id: int, files: list[Upload]) -> dict[str, Any]:
    response = client.post(
        f"/api/datasets/{dataset_id}/images",
        files=[("files", (name, data, "application/octet-stream")) for name, data in files],
    )
    assert response.status_code == 200, response.text
    result: dict[str, Any] = response.json()
    return result


def detail(client: TestClient, dataset_id: int) -> dict[str, Any]:
    result: dict[str, Any] = client.get(f"/api/datasets/{dataset_id}").json()
    return result


def test_dataset_crud(client: TestClient, settings: Settings) -> None:
    dataset = create(client, description="Tabby cats", target_resolution=768)
    assert (dataset["image_count"], dataset["target_resolution"]) == (0, 768)

    upload(client, dataset["id"], [("a.png", encode(picture(1)))])
    folder = settings.dataset_directory / str(dataset["id"])
    assert any(folder.rglob("*.png"))

    renamed = client.patch(f"/api/datasets/{dataset['id']}", json={"name": "Tabbies"}).json()
    assert renamed["name"] == "Tabbies"
    summaries = client.get("/api/datasets").json()
    assert [(s["name"], s["image_count"]) for s in summaries] == [("Tabbies", 1)]
    assert summaries[0]["cover_thumbnail_url"].endswith("/thumbnail")

    assert client.delete(f"/api/datasets/{dataset['id']}").status_code == 204
    assert client.get(f"/api/datasets/{dataset['id']}").status_code == 404
    assert not folder.exists()


def test_create_validation(client: TestClient) -> None:
    assert client.post("/api/datasets", json={"name": ""}).status_code == 422
    bad = client.post("/api/datasets", json={"name": "x", "target_resolution": 100})
    assert bad.status_code == 422


def test_upload_mixed_batch(client: TestClient) -> None:
    dataset = create(client)
    first = encode(picture(1))
    result = upload(
        client,
        dataset["id"],
        [
            ("one.png", first),
            ("two.jpg", encode(picture(2), "JPEG")),
            ("one-again.png", first),
            ("notes.png", b"just some text pretending to be a png"),
            ("anim.gif", encode(picture(3, (64, 64)), "GIF")),
        ],
    )
    assert [image["original_filename"] for image in result["added"]] == ["one.png", "two.jpg"]
    assert {s["filename"]: s["reason"] for s in result["skipped"]} == {
        "one-again.png": "duplicate",
        "notes.png": "not_an_image",
        "anim.gif": "unsupported_format",
    }
    duplicate = next(s for s in result["skipped"] if s["reason"] == "duplicate")
    assert duplicate["message"] == "Same file as one.png."

    # A duplicate of an image uploaded earlier is also skipped.
    again = upload(client, dataset["id"], [("copy.png", first)])
    assert again["added"] == []
    assert again["skipped"][0]["message"] == "Same file as one.png."
    assert detail(client, dataset["id"])["image_count"] == 2


def test_upload_limits(settings: Settings) -> None:
    small = settings.model_copy(update={"max_image_upload_mb": 1})
    with TestClient(create_app(small)) as client:
        dataset = create(client)
        noise = Image.effect_noise((1024, 1024), 100).convert("RGB")
        result = upload(client, dataset["id"], [("huge.png", encode(noise))])
        assert result["skipped"][0]["reason"] == "too_large"

        too_many = client.post(
            f"/api/datasets/{dataset['id']}/images",
            files=[("files", (f"{i}.png", b"x", "image/png")) for i in range(51)],
        )
        assert too_many.status_code == 422


def test_stored_files_never_use_client_names(client: TestClient, settings: Settings) -> None:
    dataset = create(client)
    result = upload(client, dataset["id"], [("../../../evil.png", encode(picture(1)))])
    image = result["added"][0]
    assert image["original_filename"] == "evil.png"

    folder = (settings.dataset_directory / str(dataset["id"])).resolve()
    stored = [p for p in folder.rglob("*") if p.is_file()]
    assert len(stored) == 2  # image + thumbnail
    assert all(p.is_relative_to(folder) and "evil" not in p.name for p in stored)
    assert not any((settings.dataset_directory.parent).glob("evil*"))


def test_image_and_thumbnail_are_served_by_id(client: TestClient) -> None:
    dataset = create(client)
    image = upload(client, dataset["id"], [("a.jpg", encode(picture(1), "JPEG"))])["added"][0]

    full = client.get(image["url"])
    assert full.headers["content-type"] == "image/jpeg"
    assert Image.open(io.BytesIO(full.content)).size == (512, 512)
    thumb = client.get(image["thumbnail_url"])
    assert thumb.headers["content-type"] == "image/webp"

    other = create(client, name="Other")
    assert client.get(f"/api/datasets/{other['id']}/images/{image['id']}/file").status_code == 404


def test_captions(client: TestClient) -> None:
    dataset = create(client)
    added = upload(
        client, dataset["id"], [("a.png", encode(picture(1))), ("b.png", encode(picture(2)))]
    )["added"]
    assert detail(client, dataset["id"])["uncaptioned_count"] == 2

    response = client.patch(
        f"/api/datasets/{dataset['id']}/images/{added[0]['id']}",
        json={"caption": "  a tabby cat on a sofa  "},
    )
    image = response.json()
    assert image["caption"] == "a tabby cat on a sofa"
    assert image["caption_source"] == "manual"
    assert image["caption_updated_at"] is not None
    assert detail(client, dataset["id"])["uncaptioned_count"] == 1

    too_long = client.patch(
        f"/api/datasets/{dataset['id']}/images/{added[0]['id']}", json={"caption": "x" * 5001}
    )
    assert too_long.status_code == 422


def test_reorder_and_delete(client: TestClient, settings: Settings) -> None:
    dataset = create(client)
    ids = [
        image["id"]
        for image in upload(
            client, dataset["id"], [(f"{i}.png", encode(picture(i))) for i in range(3)]
        )["added"]
    ]

    reordered = client.put(
        f"/api/datasets/{dataset['id']}/order", json={"image_ids": [ids[2], ids[0], ids[1]]}
    ).json()
    assert [image["id"] for image in reordered["images"]] == [ids[2], ids[0], ids[1]]
    assert [image["position"] for image in reordered["images"]] == [0, 1, 2]

    for bad in ([ids[0], ids[1]], [ids[0], ids[0], ids[1]], [*ids, 999]):
        response = client.put(f"/api/datasets/{dataset['id']}/order", json={"image_ids": bad})
        assert response.status_code == 422

    assert client.delete(f"/api/datasets/{dataset['id']}/images/{ids[0]}").status_code == 204
    remaining = detail(client, dataset["id"])["images"]
    assert [(image["id"], image["position"]) for image in remaining] == [(ids[2], 0), (ids[1], 1)]
    folder = settings.dataset_directory / str(dataset["id"])
    assert len([p for p in folder.rglob("*") if p.is_file()]) == 4


@pytest.mark.parametrize(
    ("image", "flag"),
    [
        (picture(1, (320, 320)), "low_resolution"),
        (picture(1, (1200, 520)), "extreme_aspect_ratio"),
        (picture(1).filter(ImageFilter.GaussianBlur(4)), "possibly_blurry"),
    ],
    ids=["low-res", "aspect", "blurry"],
)
def test_quality_flags(client: TestClient, image: Image.Image, flag: str) -> None:
    dataset = create(client)
    added = upload(client, dataset["id"], [("x.png", encode(image))])["added"][0]
    assert added["flags"] == [flag]
    assert detail(client, dataset["id"])["flagged_count"] == 1


def test_flags_follow_target_resolution(client: TestClient) -> None:
    dataset = create(client, target_resolution=512)
    upload(client, dataset["id"], [("small.png", encode(picture(1, (320, 320))))])
    assert detail(client, dataset["id"])["images"][0]["flags"] == ["low_resolution"]

    client.patch(f"/api/datasets/{dataset['id']}", json={"target_resolution": 256})
    assert detail(client, dataset["id"])["images"][0]["flags"] == []


def test_near_duplicates_are_linked_both_ways(client: TestClient) -> None:
    dataset = create(client)
    added = upload(
        client,
        dataset["id"],
        [
            ("original.png", encode(picture(7, (768, 768)))),
            ("resized.jpg", encode(picture(7, (768, 768)).resize((600, 600)), "JPEG")),
            ("different.png", encode(picture(8, (768, 768)))),
        ],
    )["added"]
    assert len(added) == 3  # near-duplicates are added, only flagged
    images = {
        image["original_filename"]: image for image in detail(client, dataset["id"])["images"]
    }
    original, resized = images["original.png"], images["resized.jpg"]
    assert "near_duplicate" in original["flags"] and "near_duplicate" in resized["flags"]
    assert original["near_duplicate_of"] == [resized["id"]]
    assert resized["near_duplicate_of"] == [original["id"]]
    assert images["different.png"]["flags"] == []

    # Removing one copy clears the flag on the other.
    client.delete(f"/api/datasets/{dataset['id']}/images/{resized['id']}")
    assert detail(client, dataset["id"])["images"][0]["flags"] == []


def test_unknown_dataset_or_image(client: TestClient) -> None:
    assert client.get("/api/datasets/999").status_code == 404
    dataset = create(client)
    assert client.delete(f"/api/datasets/{dataset['id']}/images/999").status_code == 404
    response = client.post(
        "/api/datasets/999/images", files=[("files", ("a.png", encode(picture(1)), "image/png"))]
    )
    assert response.status_code == 404


def test_settings_show_dataset_directory(client: TestClient, settings: Settings) -> None:
    runtime = client.get("/api/settings").json()["runtime"]
    assert Path(runtime["dataset_directory"]) == settings.dataset_directory
