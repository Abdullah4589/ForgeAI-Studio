import struct
from pathlib import Path

import pytest

from ai.errors import InvalidLoraError, InvalidSafetensorsError
from ai.lora.inspect import inspect_lora, is_compatible
from ai.safetensors_header import read_header
from tests.helpers import SD15_LORA_TENSORS, SDXL_LORA_TENSORS, write_safetensors


def test_read_header_returns_shapes(tmp_path: Path) -> None:
    path = write_safetensors(tmp_path / "a.safetensors", {"w": [2, 3]})
    header = read_header(path)
    assert header["w"].shape == (2, 3)
    assert header["w"].dtype == "F16"


@pytest.mark.parametrize(
    "content",
    [
        b"",
        b"abc",
        struct.pack("<Q", 10**12) + b"{}",  # header length larger than file
        struct.pack("<Q", 4) + b"nope",  # not JSON
        struct.pack("<Q", 2) + b"[]",  # JSON but not an object
        struct.pack("<Q", 2) + b"{}",  # no tensors
    ],
)
def test_read_header_rejects_invalid_files(tmp_path: Path, content: bytes) -> None:
    path = tmp_path / "bad.safetensors"
    path.write_bytes(content)
    with pytest.raises(InvalidSafetensorsError):
        read_header(path)


def test_inspect_detects_sd15_lora(tmp_path: Path) -> None:
    info = inspect_lora(write_safetensors(tmp_path / "l.safetensors", SD15_LORA_TENSORS))
    assert info.architecture == "sd15"
    assert info.rank == 4


def test_inspect_detects_sdxl_lora(tmp_path: Path) -> None:
    info = inspect_lora(write_safetensors(tmp_path / "l.safetensors", SDXL_LORA_TENSORS))
    assert info.architecture == "sdxl"


def test_inspect_detects_peft_style_keys(tmp_path: Path) -> None:
    tensors = {
        "unet.down_blocks.0.attentions.0.transformer_blocks.0.attn2.to_k.lora_A.weight": [8, 2048]
    }
    info = inspect_lora(write_safetensors(tmp_path / "l.safetensors", tensors))
    assert info.architecture == "sdxl"


def test_inspect_unknown_architecture(tmp_path: Path) -> None:
    tensors = {"lora_unet_mid_block_attentions_0_proj_in.lora_down.weight": [4, 1280]}
    assert (
        inspect_lora(write_safetensors(tmp_path / "l.safetensors", tensors)).architecture
        == "unknown"
    )


def test_inspect_rejects_non_lora(tmp_path: Path) -> None:
    path = write_safetensors(tmp_path / "model.safetensors", {"model.diffusion_model.w": [4, 4]})
    with pytest.raises(InvalidLoraError):
        inspect_lora(path)


def test_inspect_wraps_corrupt_file_error(tmp_path: Path) -> None:
    path = tmp_path / "x.safetensors"
    path.write_bytes(b"garbage")
    with pytest.raises(InvalidLoraError):
        inspect_lora(path)


@pytest.mark.parametrize(
    ("lora", "model", "expected"),
    [
        ("sd15", "sd15", True),
        ("sdxl", "sd15", False),
        ("sd15", "sdxl", False),
        ("unknown", "sdxl", True),
    ],
)
def test_is_compatible(lora: str, model: str, expected: bool) -> None:
    assert is_compatible(lora, model) is expected
