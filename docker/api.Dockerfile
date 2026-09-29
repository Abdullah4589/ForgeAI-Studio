# ForgeAI Studio API. CPU by default; for NVIDIA GPUs see docs/gpu-docker.md.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/app/apps/api:/app

WORKDIR /app

# CPU wheels by default; docker-compose.gpu.yml switches this to a CUDA wheel index.
ARG TORCH_INDEX_URL=https://download.pytorch.org/whl/cpu

# Install dependencies only (via a stub package) so code changes don't invalidate this layer.
# The app itself runs from source on PYTHONPATH, which keeps apps/api/migrations next to it.
COPY pyproject.toml README.md ./
RUN mkdir -p apps/api/forge_api ai \
    && touch apps/api/forge_api/__init__.py ai/__init__.py \
    && pip install torch --index-url "$TORCH_INDEX_URL" \
    && pip install ".[ai,postgres]" \
    && pip uninstall -y forge-ai-studio \
    && rm -rf apps ai

COPY alembic.ini ./
COPY ai ./ai
COPY apps/api ./apps/api

RUN useradd --create-home --uid 1000 forge && mkdir -p /app/storage && chown -R forge /app/storage
USER forge

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/health')"
CMD ["uvicorn", "forge_api.main:app", "--host", "0.0.0.0", "--port", "8000"]
