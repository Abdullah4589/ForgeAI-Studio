import importlib.util
from fnmatch import fnmatch
from pathlib import Path
from types import ModuleType

SCRIPT = Path(__file__).parents[2] / "scripts" / "download_model.py"

# File listing of a real Diffusers repo that also ships single-file checkpoints at its top level.
REPO_FILES = [
    "README.md",
    "Realistic_Vision_V5.1.ckpt",
    "Realistic_Vision_V5.1.safetensors",
    "Realistic_Vision_V5.1_fp16-no-ema.safetensors",
    "model_index.json",
    "scheduler/scheduler_config.json",
    "text_encoder/config.json",
    "text_encoder/model.fp16.safetensors",
    "text_encoder/model.safetensors",
    "text_encoder/pytorch_model.bin",
    "tokenizer/merges.txt",
    "tokenizer/vocab.json",
    "unet/config.json",
    "unet/diffusion_pytorch_model.safetensors",
    "vae/config.json",
    "vae/diffusion_pytorch_model.safetensors",
]


def _load_script() -> ModuleType:
    spec = importlib.util.spec_from_file_location("download_model", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _selected(files: list[str], allow: list[str], ignore: list[str]) -> list[str]:
    # Same rule as huggingface_hub's snapshot_download: fnmatch against allow, then ignore.
    return [
        name
        for name in files
        if any(fnmatch(name, pattern) for pattern in allow)
        and not any(fnmatch(name, pattern) for pattern in ignore)
    ]


def test_model_download_skips_top_level_checkpoints_and_unsafe_weights() -> None:
    script = _load_script()
    selected = _selected(REPO_FILES, script.MODEL_ALLOW_PATTERNS, script.IGNORE_PATTERNS)
    assert selected == [
        "model_index.json",
        "scheduler/scheduler_config.json",
        "text_encoder/config.json",
        "text_encoder/model.safetensors",
        "tokenizer/merges.txt",
        "tokenizer/vocab.json",
        "unet/config.json",
        "unet/diffusion_pytorch_model.safetensors",
        "vae/config.json",
        "vae/diffusion_pytorch_model.safetensors",
    ]


def test_captioner_download_keeps_top_level_weights() -> None:
    script = _load_script()
    files = ["config.json", "model.safetensors", "pytorch_model.bin", "modeling_florence2.py"]
    selected = _selected(files, script.CAPTIONER_ALLOW_PATTERNS, script.IGNORE_PATTERNS)
    assert selected == ["config.json", "model.safetensors"]
