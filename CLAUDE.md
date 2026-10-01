# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

ForgeAI Studio is a self-hosted image-generation studio: a Next.js UI (`apps/web`) over a FastAPI
API (`apps/api/forge_api`) that drives Hugging Face Diffusers through a framework-free AI layer
(`ai/`). Project conventions and safety rules are in AGENTS.md, imported here:

@AGENTS.md

## Commands

Backend commands run from the **repo root** with the venv active (`.venv\Scripts\activate` on
Windows, `source .venv/bin/activate` elsewhere). Paths such as `./storage` and the pytest/mypy
config in `pyproject.toml` are relative to the root.

```bash
# Run (two terminals). The API applies Alembic migrations on startup.
uvicorn forge_api.main:app --app-dir apps/api --reload --port 8000
cd apps/web && npm run dev                      # http://localhost:3000

# Backend checks
ruff check . && ruff format --check . && mypy && pytest
pytest tests/unit/test_storage.py                              # one file
pytest tests/integration/test_api.py::test_name                # one test
pytest -k "lora and not import"                                # by keyword

# Frontend checks (apps/web)
npm run lint && npm run typecheck && npm run format:check && npm test && npm run build
npx vitest run src/lib/api.test.ts -t "builds history"         # one Vitest file / test
npx playwright test e2e/compare.spec.ts -g "seeds"             # one E2E spec / test
```

- **No model or GPU needed for tests.** `tests/conftest.py` builds the app with
  `create_app(Settings(...))` using the mock generation, caption and training backends and a
  temporary SQLite database. To develop the UI without weights, export `GENERATION_BACKEND=mock`,
  `CAPTION_BACKEND=mock` and `TRAINING_BACKEND=mock` before starting the API.
- **Playwright starts its own servers**: `e2e/start-api.mjs` launches the API in mock mode on port
  8001 with a throwaway `e2e/.e2e-storage` folder, and the web app on port 3100. Specs run
  serially (`workers: 1`) because they share one database.
- **`CI=1 npx playwright test` runs `next build`** with the E2E API URL baked in
  (`NEXT_PUBLIC_API_URL` is inlined at build time). Rebuild before serving the real app with
  `npm run start` afterwards.
- **Real-model test (opt-in):** `FORGE_REAL_TRAINING=1 pytest tests/integration/test_training_real.py`
  needs the `[ai]` extra and `storage/models/bk-sdm-tiny`.
- **Schema changes:** add a numbered revision under `apps/api/migrations/versions/` (`alembic.ini`
  is at the repo root). CI also runs the migrations against PostgreSQL, so keep them portable
  (SQLite uses `render_as_batch`).
- **Models:** `python scripts/download_model.py [repo-id] [--name folder]` and `--captioner`.

## Architecture

Dependencies point one way: `apps/web` → HTTP → `forge_api` → `ai`. The `ai` package never imports
`forge_api`, and never imports torch/diffusers at module level.

**App wiring.** `forge_api/main.py::build_services` creates everything once (engine, device,
`ModelManager`, generation backend, captioner, `JobManager`) into an `AppServices` container
stored on `app.state.services`. Routes receive it through `dependencies.py` and delegate to
`services/*`; routes hold no logic. On startup the app syncs `storage/models` and `storage/loras`
into the database and marks comparisons and training runs left "running" by a previous process as
interrupted.

**One job at a time.** Generation, comparison, captioning and training all go through
`jobs/manager.py::JobManager`: one worker thread, in-process, FIFO. Starting a second job while
one is active is rejected with `409` (`generation_service.ensure_idle`). A job reports progress
through `JobContext`; each change bumps `Job.version`, which the SSE endpoint
(`GET /api/jobs/{id}/events`) watches. Cancellation is cooperative via `cancel_event`
(`POST /api/generate/cancel` takes a job id and works for every job kind). When the queue has been idle for
`MODEL_IDLE_UNLOAD_SECONDS`, the manager calls back to release the loaded models.

**Swappable backends.** Each heavy capability has a protocol, a real implementation and a mock,
selected by an environment variable through a factory: `ai/generation` (`GENERATION_BACKEND`),
`ai/captioning` (`CAPTION_BACKEND`), `ai/training` (`TRAINING_BACKEND`). Mocks are for tests, CI
and UI work only.

**Model memory.** `ai/model_manager/manager.py` keeps at most one pipeline loaded; loading another
unloads the first. A generation holds the manager's lock for its whole run, so anything on a
request path that only needs to know what is loaded must use the lock-free `loaded_request()`
rather than take the lock (taking it made `/api/models` hang for minutes).

**Training is a separate process.** `ai/training/runner.py` spawns
`python -m ai.training.worker <config.json> <cancel-flag>` and reads JSON lines prefixed with
`@@forge-training ` (`protocol.py`) from its stdout; cancelling creates the flag file, with a
forced kill after a grace period. `training_service` relays progress to the job and database and
registers the resulting LoRA.

**Comparisons are generations.** A comparison varies one axis (LoRA strength, seed or model); each
cell is a normal `Generation` row with `comparison_id`, produced by the same
`generation_service.prepare()` / `execute()` as a single generation.

**Frontend.** `src/lib/api.ts` is the only module that calls the API, and `src/lib/types.ts`
mirrors the response schemas. `src/hooks/useJob.ts` is the single job-tracking hook (SSE with a
polling fallback, elapsed time, cancel, reattaching to a job after reload) used by every page that
starts a job. The `src/lib/*-form.ts`, `captions.ts` and `training.ts` modules duplicate backend
validation limits and rules on purpose, so a change to a Pydantic schema or to
`caption_service.should_caption()` needs the matching frontend change. `apps/web` runs Next.js 16,
whose APIs differ from older versions: see `apps/web/AGENTS.md`.

## CI

`.github/workflows/ci.yml` runs five jobs: backend (ruff, mypy, pytest), migrations on PostgreSQL,
frontend (ESLint, tsc, Prettier, Vitest, build), Playwright E2E against the mock backends, and
Docker image builds. There is no GPU in CI: CUDA code paths are covered by unit tests with fakes
only.
