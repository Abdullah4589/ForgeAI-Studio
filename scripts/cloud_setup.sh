#!/usr/bin/env bash
# Set up and start the ForgeAI Studio API on a Linux machine with an NVIDIA GPU.
# Written for a Lightning AI Studio; see docs/cloud-gpu.md. Safe to run again: finished steps
# are skipped.
#
# Usage: bash scripts/cloud_setup.sh [model-repo-id] [folder-name]
set -euo pipefail

MODEL_REPO="${1:-SG161222/Realistic_Vision_V5.1_noVAE}"
MODEL_NAME="${2:-${MODEL_REPO##*/}}"
PORT="${PORT:-8000}"

cd "$(dirname "$0")/.."

if ! nvidia-smi >/dev/null 2>&1; then
  echo "No NVIDIA GPU found. Switch this machine to a GPU first, then run the script again." >&2
  exit 1
fi

if [ ! -x .venv/bin/python ]; then
  if python3 -c 'import sys; sys.exit(sys.version_info < (3, 12))' 2>/dev/null; then
    python3 -m venv .venv
  else
    # The project needs Python 3.12+; uv fetches one without touching the system Python.
    python3 -m pip install --quiet uv
    python3 -m uv venv --seed --python 3.12 .venv
  fi
fi

# On Linux the default PyTorch wheel includes CUDA support, so no extra index is needed.
.venv/bin/python -m pip install --quiet -e ".[ai]"

if ! .venv/bin/python -c 'import sys, torch; sys.exit(not torch.cuda.is_available())'; then
  echo "PyTorch cannot use the GPU. Check 'nvidia-smi' and the installed torch build." >&2
  exit 1
fi

if [ ! -f "storage/models/$MODEL_NAME/model_index.json" ]; then
  .venv/bin/python scripts/download_model.py "$MODEL_REPO" --name "$MODEL_NAME"
fi

echo "Starting the API on port $PORT. Leave this terminal open; press Ctrl+C to stop."
# Bound to localhost on purpose: the API has no authentication, so reach it through an SSH
# tunnel instead of a public URL.
exec .venv/bin/python -m uvicorn forge_api.main:app --app-dir apps/api --host 127.0.0.1 --port "$PORT"
