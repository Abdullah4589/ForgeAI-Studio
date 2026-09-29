from pathlib import Path

from ai.model_manager.discovery import scan_models
from tests.helpers import write_diffusers_model, write_safetensors


def test_scan_missing_directory_returns_empty(tmp_path: Path) -> None:
    assert scan_models(tmp_path / "nope") == []


def test_scan_finds_diffusers_folders_with_architecture(tmp_path: Path) -> None:
    write_diffusers_model(tmp_path, "sd-model", "StableDiffusionPipeline")
    write_diffusers_model(tmp_path, "xl_model", "StableDiffusionXLPipeline")
    write_diffusers_model(tmp_path, "other", "FluxPipeline")
    (tmp_path / "not-a-model").mkdir()

    found = {m.path.name: m for m in scan_models(tmp_path)}

    assert set(found) == {"sd-model", "xl_model", "other"}
    assert found["sd-model"].architecture == "sd15"
    assert found["sd-model"].name == "sd model"
    assert found["sd-model"].supported_resolutions[0] == (512, 512)
    assert found["xl_model"].architecture == "sdxl"
    assert found["other"].architecture == "unknown"
    assert found["other"].supported_resolutions == []


def test_scan_identifies_single_file_checkpoints(tmp_path: Path) -> None:
    write_safetensors(tmp_path / "v15.safetensors", {"cond_stage_model.transformer.w": [2]})
    write_safetensors(tmp_path / "xl.safetensors", {"conditioner.embedders.1.model.w": [2]})
    (tmp_path / "broken.safetensors").write_bytes(b"not a safetensors file")
    (tmp_path / "weights.ckpt").write_bytes(b"pickle is never scanned")

    found = {m.path.name: m for m in scan_models(tmp_path)}

    assert set(found) == {"v15.safetensors", "xl.safetensors"}
    assert found["v15.safetensors"].architecture == "sd15"
    assert found["v15.safetensors"].source_type == "single_file"
    assert found["xl.safetensors"].architecture == "sdxl"


def test_corrupt_model_index_yields_unknown(tmp_path: Path) -> None:
    folder = tmp_path / "bad"
    folder.mkdir()
    (folder / "model_index.json").write_text("{not json")
    (model,) = scan_models(tmp_path)
    assert model.architecture == "unknown"
