"""Download a Diffusers model from the Hugging Face Hub into the model directory.

Only configs, tokenizer files and fp32 `.safetensors` weights are fetched; pickle-based `.bin`
weights are skipped because ForgeAI Studio refuses to load them.

Usage:
    python scripts/download_model.py                      # small SD 1.x test model
    python scripts/download_model.py <repo-id> [--name folder-name]
"""

import argparse
import sys
from pathlib import Path

DEFAULT_REPO = "nota-ai/bk-sdm-tiny"
ALLOW_PATTERNS = ["*.json", "*.txt", "*.safetensors"]
IGNORE_PATTERNS = ["*.bin", "*.fp16.safetensors", "*.ckpt", "*.pt", "*.pth", ".ipynb_checkpoints/*"]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("repo_id", nargs="?", default=DEFAULT_REPO)
    parser.add_argument("--name", help="Folder name inside the model directory.")
    parser.add_argument("--model-dir", default="storage/models", type=Path)
    args = parser.parse_args()

    try:
        from huggingface_hub import snapshot_download
    except ImportError:
        print('huggingface_hub is missing. Install the AI extra: pip install -e ".[ai]"')
        return 1

    target = args.model_dir / (args.name or args.repo_id.split("/")[-1])
    print(f"Downloading {args.repo_id} into {target} ...")
    snapshot_download(
        repo_id=args.repo_id,
        local_dir=target,
        allow_patterns=ALLOW_PATTERNS,
        ignore_patterns=IGNORE_PATTERNS,
    )
    if not (target / "model_index.json").is_file():
        print("Downloaded files do not include model_index.json; this is not a Diffusers model.")
        return 1
    print("Done. Press Rescan on the Models page (or restart the API) to pick it up.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
