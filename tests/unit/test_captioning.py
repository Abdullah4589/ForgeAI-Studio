import sys
import types
from pathlib import Path
from typing import Any

import pytest
from PIL import Image

from ai.captioning.cleanup import clean_caption
from ai.captioning.florence import TASK, FlorenceCaptioner
from ai.captioning.mock import MockCaptioner
from ai.errors import ModelLoadError
from forge_api.db.models import DatasetImage
from forge_api.services.caption_service import plan, should_caption


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("The image shows a painting of a lighthouse.", "a painting of a lighthouse."),
        ("This image depicts  a red\n house in the woods", "a red house in the woods"),
        ("The picture is an oil painting", "an oil painting"),
        ("A cat on a sofa.", "a cat on a sofa."),
        ("NASA rocket on a launch pad", "NASA rocket on a launch pad"),
        ("Paris at night, oil painting", "Paris at night, oil painting"),
        ("The Eiffel Tower at dusk", "the Eiffel Tower at dusk"),
        ("  ", ""),
    ],
)
def test_clean_caption(raw: str, expected: str) -> None:
    assert clean_caption(raw) == expected


def image(caption: str = "", source: str | None = None, id: int = 1) -> DatasetImage:
    return DatasetImage(id=id, caption=caption, caption_source=source)


@pytest.mark.parametrize(
    ("img", "mode", "expected"),
    [
        (image(), "empty_only", True),
        (image("ai text", "ai"), "empty_only", False),
        (image("ai text", "ai"), "replace_ai", True),
        (image("mine", "manual"), "replace_ai", False),
        (image("mine", "manual"), "everything", True),
        (image("unknown origin", None), "replace_ai", False),
    ],
)
def test_should_caption(img: DatasetImage, mode: Any, expected: bool) -> None:
    assert should_caption(img, mode) is expected


def test_plan_counts_what_is_protected() -> None:
    images = [
        image(id=1),
        image("ai text", "ai", id=2),
        image("mine", "manual", id=3),
        image("mine too", "manual", id=4),
    ]
    result = plan(images, "empty_only")
    assert (result.image_ids, result.skipped_existing, result.skipped_manual) == ([1], 1, 2)
    assert plan(images, "replace_ai").image_ids == [1, 2]
    assert plan(images, "everything").image_ids == [1, 2, 3, 4]


def test_mock_captioner_is_deterministic() -> None:
    red = Image.new("RGB", (64, 32), (210, 50, 50))
    captioner = MockCaptioner()
    assert captioner.caption(red) == captioner.caption(red.copy())
    assert "64x32 red" in captioner.caption(red)
    assert "blue" in captioner.caption(Image.new("RGB", (8, 8), (40, 70, 220)))


def test_florence_reports_missing_model(tmp_path: Path) -> None:
    with pytest.raises(ModelLoadError, match=r"download_model\.py --captioner"):
        FlorenceCaptioner(tmp_path / "nothing-here", "cpu").caption(Image.new("RGB", (8, 8)))


# ---- Florence with fake transformers/torch ------------------------------------------------


class FakeTensor:
    def to(self, *_: Any, **__: Any) -> "FakeTensor":
        return self


@pytest.fixture
def fake_stack(monkeypatch: pytest.MonkeyPatch) -> types.SimpleNamespace:
    calls: dict[str, Any] = {"loads": 0}

    class FakeModel:
        dtype = "float32"

        def to(self, device: str) -> "FakeModel":
            calls["device"] = device
            return self

        def eval(self) -> "FakeModel":
            return self

        def generate(self, **kwargs: Any) -> list[str]:
            calls["generate"] = kwargs
            return ["raw-ids"]

    class FakeProcessor:
        def __call__(self, text: str, images: Image.Image, return_tensors: str) -> dict[str, Any]:
            calls["task"] = text
            return {"input_ids": FakeTensor(), "pixel_values": FakeTensor()}

        def batch_decode(self, ids: list[str], skip_special_tokens: bool) -> list[str]:
            return ["</s>The image shows a lighthouse.</s>"]

        def post_process_generation(
            self, text: str, task: str, image_size: tuple[int, int]
        ) -> dict[str, str]:
            return {task: "The image shows a lighthouse."}

    def load_model(path: str, **kwargs: Any) -> FakeModel:
        calls["loads"] += 1
        calls["load_kwargs"] = kwargs
        return FakeModel()

    transformers = types.SimpleNamespace(
        Florence2ForConditionalGeneration=types.SimpleNamespace(from_pretrained=load_model),
        AutoProcessor=types.SimpleNamespace(from_pretrained=lambda path: FakeProcessor()),
    )
    torch = types.SimpleNamespace(
        float16="float16",
        float32="float32",
        inference_mode=lambda: _NullContext(),
        cuda=types.SimpleNamespace(is_available=lambda: False),
    )
    monkeypatch.setitem(sys.modules, "transformers", transformers)
    monkeypatch.setitem(sys.modules, "torch", torch)
    return types.SimpleNamespace(calls=calls)


class _NullContext:
    def __enter__(self) -> None:
        return None

    def __exit__(self, *_: object) -> None:
        return None


def model_dir(tmp_path: Path) -> Path:
    folder = tmp_path / "florence-2-base"
    folder.mkdir()
    (folder / "config.json").write_text("{}")
    return folder


def test_florence_captions_and_loads_once(tmp_path: Path, fake_stack: Any) -> None:
    captioner = FlorenceCaptioner(model_dir(tmp_path), "cpu")
    assert captioner.name == "florence-2-base"
    first = captioner.caption(Image.new("RGB", (16, 16)))
    captioner.caption(Image.new("RGB", (16, 16)))

    assert first == "The image shows a lighthouse."  # cleaned later by the service
    calls = fake_stack.calls
    assert calls["loads"] == 1
    assert calls["task"] == TASK
    assert calls["load_kwargs"] == {"dtype": "float32", "use_safetensors": True}
    assert calls["generate"]["do_sample"] is False


def test_florence_release_forces_reload(tmp_path: Path, fake_stack: Any) -> None:
    captioner = FlorenceCaptioner(model_dir(tmp_path), "cpu")
    captioner.release()  # no-op before loading
    captioner.caption(Image.new("RGB", (16, 16)))
    captioner.release()
    captioner.caption(Image.new("RGB", (16, 16)))
    assert fake_stack.calls["loads"] == 2
