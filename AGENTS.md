# AGENTS.md

Guidance for AI coding agents and contributors working on ForgeAI Studio.

## Current phase

**Phase 1 (MVP) is complete.** Do not start Phase 2+ work (comparison mode, datasets, captioning,
LoRA training) unless explicitly asked. See the roadmap in `README.md` and the full specification
in `Forge_AI_Studio.md`.

## Layout

| Path | What lives there |
| --- | --- |
| `apps/api/forge_api/` | FastAPI app. `routes/` are thin; logic lives in `services/`. `jobs/` is the in-process job queue. |
| `apps/api/migrations/` | Alembic migrations. Never use `create_all()`; add a revision for every schema change. |
| `ai/` | Framework-free AI layer: device selection, model discovery/manager, pipelines registry, LoRA inspection/apply, generation backends. Must not import `forge_api`. |
| `apps/web/` | Next.js 16 (App Router) + Tailwind v4 UI. `src/lib/api.ts` is the only place that calls the API. |
| `apps/web/e2e/` | Playwright tests (run against the API in mock mode). |
| `tests/unit`, `tests/integration` | Pytest suites. |

## Rules that matter here

- **Torch/diffusers are optional imports.** Import them lazily inside functions so the API, tests
  and CI run without the `[ai]` extra.
- **Never load pickle weights.** Use `use_safetensors=True`; LoRAs must be `.safetensors` and are
  inspected by parsing the header only (`ai/safetensors_header.py`).
- **Untrusted paths:** always go through `forge_api/services/storage.py` (`safe_filename`,
  `resolve_within`). Images are served by DB id, never by client-supplied path.
- **User-facing errors:** raise `ai.errors.*` / `forge_api.errors.*` with a friendly message;
  stack traces go to logs only.
- **Mock backend** (`GENERATION_BACKEND=mock`) exists for tests/CI/UI work. Never use it to fake
  production behaviour.
- New architectures: add an `ArchitectureSpec` in `ai/pipelines/registry.py` plus detection.
- Keep frontend validation limits in `apps/web/src/lib/generation-form.ts` in sync with
  `apps/api/forge_api/schemas/generation.py`.

## Checks (run before committing)

```bash
# backend (repo root, venv active)
ruff check . && ruff format --check . && mypy && pytest

# frontend (apps/web)
npm run lint && npm run typecheck && npm run format:check && npm test && npm run build
npx playwright test
```
