"""Download a model from the Hugging Face Hub into ForgeAI Studio's storage.

Only configs, tokenizer files and fp32 `.safetensors` weights are fetched; pickle-based `.bin`
weights and repository code files are skipped because ForgeAI Studio refuses to load them.

Usage:
    python scripts/download_model.py                      # small SD 1.x test model
    python scripts/download_model.py <repo-id> [--name folder-name]
    python scripts/download_model.py --captioner          # Florence-2 caption model
"""

import argparse
import sys
from pathlib import Path

DEFAULT_REPO = "nota-ai/bk-sdm-tiny"
# Natively supported by Transformers, so no repository code is executed.
CAPTIONER_REPO = "florence-community/Florence-2-base"
CAPTIONER_FOLDER = "florence-2-base"

_CONFIG_PATTERNS = ["*.json", "*.txt", "*.jinja", "*.model"]
# A Diffusers repo keeps its weights in component folders (unet/, vae/, ...). Many also ship the
# same model again as multi-GB single-file checkpoints at the top level; "*/" skips those.
MODEL_ALLOW_PATTERNS = [*_CONFIG_PATTERNS, "*/*.safetensors"]
# The caption model's weights sit at the top level of its repo.
CAPTIONER_ALLOW_PATTERNS = [*_CONFIG_PATTERNS, "*.safetensors"]
IGNORE_PATTERNS = [
    "*.bin",
    "*.fp16.safetensors",
    "*.ckpt",
    "*.pt",
    "*.pth",
    "*.onnx",
    "onnx/*",
    "*.py",
    ".ipynb_checkpoints/*",
]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("repo_id", nargs="?", help=f"Default: {DEFAULT_REPO}")
    parser.add_argument("--name", help="Folder name to download into.")
    parser.add_argument(
        "--captioner",
        action="store_true",
        help=f"Download the caption model ({CAPTIONER_REPO}) into storage/captioners.",
    )
    args = parser.parse_args()

    try:
        from huggingface_hub import snapshot_download
    except ImportError:
        print('huggingface_hub is missing. Install the AI extra: pip install -e ".[ai]"')
        return 1

    if args.captioner:
        repo_id = args.repo_id or CAPTIONER_REPO
        target = Path("storage/captioners") / (args.name or CAPTIONER_FOLDER)
        expected = "config.json"
        allow_patterns = CAPTIONER_ALLOW_PATTERNS
    else:
        repo_id = args.repo_id or DEFAULT_REPO
        target = Path("storage/models") / (args.name or repo_id.split("/")[-1])
        expected = "model_index.json"
        allow_patterns = MODEL_ALLOW_PATTERNS

    print(f"Downloading {repo_id} into {target} ...")
    snapshot_download(
        repo_id=repo_id,
        local_dir=target,
        allow_patterns=allow_patterns,
        ignore_patterns=IGNORE_PATTERNS,
    )
    if not (target / expected).is_file():
        print(f"Downloaded files do not include {expected}; this is not the expected model type.")
        return 1
    if args.captioner:
        print("Done. Restart the API (or set CAPTION_MODEL_DIRECTORY) to use it.")
    else:
        print("Done. Press Rescan on the Models page (or restart the API) to pick it up.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
