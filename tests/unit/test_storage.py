from pathlib import Path

import pytest

from forge_api.errors import UnprocessableError
from forge_api.services.storage import resolve_within, safe_filename


@pytest.mark.parametrize(
    ("original", "expected"),
    [
        ("style.safetensors", "style.safetensors"),
        ("My Style (v2).safetensors", "My_Style_v2.safetensors"),
        ("../../etc/evil.safetensors", "evil.safetensors"),
        ("..\\..\\Windows\\evil.safetensors", "evil.safetensors"),
        (".hidden.safetensors", "hidden.safetensors"),
        ("café.SAFETENSORS", "cafe.safetensors"),
    ],
)
def test_safe_filename_sanitises(original: str, expected: str) -> None:
    assert safe_filename(original, required_suffix=".safetensors") == expected


@pytest.mark.parametrize(
    "original", ["model.ckpt", "model.bin", "noext", "...safetensors", ".safetensors"]
)
def test_safe_filename_rejects(original: str) -> None:
    with pytest.raises(UnprocessableError):
        safe_filename(original, required_suffix=".safetensors")


def test_safe_filename_truncates_long_names() -> None:
    name = safe_filename("a" * 500 + ".safetensors", required_suffix=".safetensors")
    assert len(name) <= 128
    assert name.endswith(".safetensors")


def test_resolve_within_allows_nested(tmp_path: Path) -> None:
    assert resolve_within(tmp_path, "a/b.png") == (tmp_path / "a" / "b.png").resolve()


@pytest.mark.parametrize("relative", ["../escape.png", "a/../../escape.png", "/etc/passwd"])
def test_resolve_within_blocks_traversal(tmp_path: Path, relative: str) -> None:
    with pytest.raises(UnprocessableError):
        resolve_within(tmp_path / "base", relative)
