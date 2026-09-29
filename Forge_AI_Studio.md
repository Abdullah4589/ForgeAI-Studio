# ForgeAI Studio

Build a production-quality full-stack application called **ForgeAI Studio**.

## Goal

ForgeAI Studio is a self-hosted web application for generating images with open-source diffusion models, loading and managing LoRA adapters, comparing generations, saving generation history, and later supporting custom LoRA training.

This should be built as a serious portfolio project, not a basic demo.

The project should demonstrate:

- Open-source AI model integration
- Image generation
- LoRA adapter loading
- Model management
- AI-assisted workflows
- Good software architecture
- Testing
- Docker
- CI/CD
- Production-ready coding practices

---

## Tech Stack

### Frontend

Use:

- Next.js
- TypeScript
- Tailwind CSS
- Modern component architecture
- Responsive design

### Backend

Use:

- Python
- FastAPI
- Pydantic
- REST API
- WebSocket or Server-Sent Events where useful for generation progress

### AI

Use:

- PyTorch
- Hugging Face Diffusers
- PEFT where appropriate
- Safetensors
- CUDA support when available

### Database

Start with SQLite for local development, but structure the database layer so PostgreSQL can be used later.

Use an ORM such as SQLAlchemy.

### Testing

Use:

- Pytest for backend
- Vitest/Jest where appropriate
- Playwright for end-to-end testing

### DevOps

Use:

- Docker
- Docker Compose
- GitHub Actions
- `.env.example`
- Structured logging
- Proper error handling

---

# Critical Development Strategy

**Do NOT try to build all phases in one shot.**

This full specification is provided so you understand the final direction of the product, but development must happen incrementally.

The priority is to build a **small, complete, working vertical slice first**, validate it thoroughly, and only then move on to additional phases.

Do not create large amounts of unfinished code for future features.

Do not scaffold fake implementations just to make later phases appear complete.

Do not start LoRA training, AI captioning, advanced model management, or other later features until the core Phase 1 workflow is fully working and tested.

The development sequence must be:

```text
Phase 1
Build
↓
Run
↓
Test
↓
Fix
↓
Verify manually
↓
Stabilize
↓
Commit-ready state
↓
Only then move to Phase 2
```

For every phase:

1. Understand the requirements.
2. Inspect the current codebase.
3. Create a short implementation plan.
4. Implement the smallest complete vertical slice.
5. Run linting and type checks.
6. Run unit and integration tests.
7. Run Playwright E2E tests where appropriate.
8. Fix all important failures.
9. Manually verify the main user workflow.
10. Update documentation.
11. Keep the project in a runnable, commit-ready state.
12. Only then begin the next phase.

A smaller working implementation is always preferred over a larger half-working implementation.

Never sacrifice reliability just to implement more features.

---

# Phase 1 — MVP

Build the MVP first.

Do NOT attempt LoRA training until the image-generation workflow is stable.

The MVP must allow a user to:

1. Open ForgeAI Studio in a browser.
2. Select an installed base model.
3. Select an installed LoRA if available.
4. Enter a positive prompt.
5. Enter an optional negative prompt.
6. Configure:
   - Width
   - Height
   - Seed
   - Inference steps
   - Guidance scale if supported
   - Number of images
   - LoRA strength
7. Click **Generate**.
8. See generation progress.
9. View generated images.
10. Download generated images.
11. Save every generation to history.
12. Reuse the settings of a previous generation.

---

# UI Requirements

Create a modern dark AI-tool interface.

The main generation page should roughly have:

- Left sidebar for models and navigation
- Main prompt/settings panel
- Large image preview area
- Generation history panel or page

Navigation:

- Generate
- Models
- LoRAs
- History
- System
- Settings

## Prompt Section

Include:

- Positive prompt
- Negative prompt
- Prompt character count
- Clear button

## Model Section

Include:

- Base model dropdown
- LoRA dropdown
- LoRA strength slider

## Generation Settings

Include:

- Width
- Height
- Steps
- Guidance scale
- Seed
- Random seed button
- Number of images

## Generation Area

Include:

- Generate button
- Cancel button
- Progress indicator
- Current generation status
- Generation duration
- Error display if generation fails

## Result Viewer

Display generated images in a responsive grid.

Each image should have actions:

- Download
- Reuse settings
- Copy prompt
- View metadata
- Delete

---

# Model Management

Create a model management system.

The app should scan configured model directories and identify installed models.

Store metadata such as:

- Model name
- Model ID
- Path
- Architecture
- File size
- Date added
- Description
- Preview image
- Supported resolutions

Models must NOT be loaded into GPU memory permanently.

Implement model loading and unloading safely.

Avoid unnecessary GPU memory usage.

---

# LoRA Management

Create a dedicated LoRA manager.

Users should be able to:

- View installed LoRAs
- Import a `.safetensors` LoRA
- Delete LoRAs
- Enable or disable LoRAs
- Adjust LoRA strength
- Store trigger words
- Store description
- Store preview image
- Track the compatible base model

Never blindly load incompatible adapters.

Validate LoRA compatibility where possible.

---

# Generation History

Every generation should be stored with:

- ID
- Timestamp
- Positive prompt
- Negative prompt
- Base model
- LoRA
- LoRA strength
- Seed
- Width
- Height
- Steps
- Guidance scale
- Generation duration
- Image path
- Model configuration
- Relevant metadata

Users must be able to:

- Search history
- Filter by model
- Filter by LoRA
- Sort by newest or oldest
- Delete generations
- Re-run a generation using the same settings

Preserve the seed so generations can be reproduced where technically possible.

---

# GPU and System Monitoring

Add a System page showing:

- GPU name
- VRAM total
- VRAM used
- VRAM available
- CUDA availability
- CUDA version
- PyTorch version
- CPU usage
- RAM usage
- Disk space

Do not crash if there is no NVIDIA GPU.

The application should gracefully support CPU mode, although generation may be slower.

---

# AI Pipeline Architecture

Do not put all AI logic inside API routes.

Use a clean architecture similar to:

```text
ai/
├── pipelines/
├── model_manager/
├── lora/
├── generation/
└── training/
```

Create clear services for:

- Model loading
- Model unloading
- Pipeline initialization
- LoRA loading
- LoRA removal
- Image generation
- Device selection
- VRAM cleanup
- Generation cancellation

Make the implementation modular enough that additional model families can be added later.

---

# Memory Management

GPU memory handling is extremely important.

Implement:

- Explicit model unloading
- CUDA cache cleanup when appropriate
- CPU offloading support where available
- Memory-efficient attention where supported
- Graceful out-of-memory handling

If generation fails because of insufficient VRAM, return a friendly message suggesting:

- Smaller resolution
- Fewer images
- CPU offloading
- Lower-memory model

Do not expose raw stack traces to normal users.

---

# API Design

Design clean API endpoints such as:

```text
GET    /api/models
POST   /api/models/load
POST   /api/models/unload

GET    /api/loras
POST   /api/loras/import
DELETE /api/loras/{id}

POST   /api/generate
POST   /api/generate/cancel

GET    /api/history
GET    /api/history/{id}
DELETE /api/history/{id}

GET    /api/system
```

Use appropriate Pydantic request and response schemas.

Validate all inputs.

---

# Safety and File Handling

Treat uploaded files as untrusted.

Implement:

- File extension validation
- File size restrictions
- Safe filenames
- Path traversal prevention
- Upload directory isolation
- Proper exception handling

Never execute arbitrary uploaded files.

Do not use unsafe deserialization methods for model uploads.

Prefer `safetensors`.

---

# Phase 2 — Comparison Mode

Only begin this phase after Phase 1 is complete, stable, tested, and manually verified.

Allow the user to enter one prompt and compare:

- Different LoRA strengths
- Different seeds
- Different models
- LoRA vs no LoRA

Example:

```text
No LoRA | LoRA 0.4 | LoRA 0.8
```

Show results side-by-side with their settings.

---

# Phase 3 — Dataset Manager

Only begin this phase after the previous phases remain stable.

Add a dataset preparation interface for future LoRA training.

Users should be able to:

- Create a dataset
- Upload images
- Remove images
- Reorder images
- Preview images
- Add or edit captions
- Detect duplicate files
- View resolution
- View file size
- Flag poor-quality files

Design this so AI captioning can be added later.

---

# Phase 4 — AI Captioning

Only implement this after the dataset manager works reliably.

Add automatic image captioning using an appropriate vision-language model.

For each training image:

- Generate a suggested caption
- Allow editing
- Support batch caption generation
- Show progress
- Never overwrite manually edited captions without confirmation

Structure the captioning service separately from the training service.

---

# Phase 5 — LoRA Training

Only implement this after generation, model loading, LoRA loading, dataset management, and captioning are stable.

Create a LoRA training interface.

Users should be able to configure:

- Dataset
- Base model
- Trigger word
- Resolution
- Rank
- Alpha
- Learning rate
- Batch size
- Training steps
- Save interval
- Seed

Display:

- Current step
- Total steps
- Progress percentage
- Loss
- Elapsed time
- GPU usage

Support training cancellation.

Save the final LoRA as `.safetensors`.

Generate sample images after training.

Do not hide training failures.

Provide understandable error messages.

---

# Background Tasks

Image generation and training must not block the main web server.

Create a job abstraction.

Jobs should have states such as:

```text
queued
running
completed
failed
cancelled
```

For the first version, an in-process worker is acceptable.

Design it so Redis/Celery or another job queue can be added later.

---

# Database Models

Create sensible entities such as:

- Model
- LoRA
- Generation
- GenerationImage
- Dataset
- DatasetImage
- TrainingJob
- ApplicationSetting

Use migrations.

Do not rely on `create_all()` as the long-term schema strategy.

---

# Logging

Use structured backend logging.

Log:

- Model loads
- Model unloads
- Generation requests
- Generation completion
- Generation failures
- LoRA imports
- Training jobs
- System errors

Never log secrets or API keys.

---

# Configuration

Use environment variables for configuration.

Provide `.env.example`.

Possible configuration:

```env
DATABASE_URL=
MODEL_DIRECTORY=
LORA_DIRECTORY=
OUTPUT_DIRECTORY=
DATASET_DIRECTORY=
DEVICE=
LOG_LEVEL=
MAX_UPLOAD_SIZE=
```

Do not commit secrets.

---

# Repository Structure

Use a clean monorepo structure similar to:

```text
forge-ai-studio/
│
├── apps/
│   ├── web/
│   └── api/
│
├── ai/
│   ├── pipelines/
│   ├── model_manager/
│   ├── lora/
│   ├── generation/
│   ├── captioning/
│   └── training/
│
├── tests/
│   ├── unit/
│   ├── integration/
│   └── e2e/
│
├── storage/
│
├── scripts/
│
├── docker/
│
├── docs/
│
├── .github/
│   └── workflows/
│
├── AGENTS.md
├── docker-compose.yml
├── .env.example
└── README.md
```

You may improve this structure if there is a technically better approach.

Do not create meaningless abstraction layers.

---

# Testing Requirements

Do not consider a feature complete simply because it compiles.

For every important feature:

1. Implement it.
2. Write appropriate tests.
3. Run the tests.
4. Fix failures.
5. Verify the user workflow.

## Backend

Use:

- Unit tests
- API tests
- Validation tests

## Frontend

Test important components and user interactions.

## E2E

Use Playwright.

At minimum test:

- Application loads
- Model can be selected
- Prompt can be entered
- Generation request can be submitted
- Validation errors appear correctly
- History page works
- Previous settings can be restored

Where real GPU generation would make automated testing impractical, provide a properly designed mocked generation backend for CI.

Do not fake production behavior just to make tests pass.

---

# GitHub Actions

Create CI workflows that:

- Install dependencies
- Run linting
- Run type checking
- Run frontend tests
- Run backend tests
- Run Playwright tests
- Build the application

CI must run without requiring a GPU.

Use mocks and fixtures for AI model execution in CI.

---

# Docker

Provide a development Docker Compose setup.

Where practical, provide:

- Frontend container
- Backend container
- Database

Document GPU container support separately.

Do not make Docker mandatory for local development.

---

# README

Create an excellent GitHub README.

It should include:

1. ForgeAI Studio logo or title
2. One-sentence description
3. Screenshots
4. Demo GIF or video placeholder
5. Feature list
6. Architecture diagram
7. Tech stack
8. Installation
9. GPU requirements
10. CPU mode explanation
11. Environment configuration
12. Running development mode
13. Running tests
14. Docker instructions
15. LoRA instructions
16. Project roadmap
17. Known limitations
18. Security considerations

Add an architecture diagram using Mermaid.

The README should make this look like a real open-source project.

---

# Coding Standards

Follow these rules throughout the project:

- TypeScript strict mode
- Python type hints
- Clear naming
- Small focused functions
- Avoid unnecessary duplication
- Avoid giant files
- Separate business logic from controllers and routes
- Validate external input
- Do not swallow exceptions
- No hardcoded credentials
- No placeholder implementations presented as finished features
- No fake API responses outside tests or development mocks
- No unnecessary dependencies

Comments should explain **why**, not obvious syntax.

---

# AI Coding Rules

You are working as an autonomous coding agent.

Before implementing a large feature:

1. Inspect the existing project.
2. Understand existing architecture.
3. Create a short implementation plan.
4. Implement the smallest complete vertical slice.
5. Run tests.
6. Fix problems.
7. Verify the actual workflow.
8. Update documentation where necessary.
9. Leave the repository in a stable state.

Do not rewrite working parts of the application without a reason.

Do not introduce a new framework or library unless it adds meaningful value.

If an architectural decision is unclear, prefer the simplest maintainable solution.

Never claim a feature works unless it has been implemented and validated.

## Very Important

Do not treat this specification as an instruction to implement every feature immediately.

It is a **roadmap, not a single execution request**.

Your current objective is always the active phase only.

Future phases should influence architecture decisions, but they must **NOT** cause you to prematurely implement future functionality.

Do not produce a huge half-working AI-generated codebase.

A clean, tested, maintainable Phase 1 is more valuable than five partially implemented phases.

---

# Current Objective — Phase 1 Only

For now, implement **ONLY Phase 1**.

The first successful milestone is:

> A user opens ForgeAI Studio, selects a locally available compatible model, enters a prompt, generates an image, sees the result in the browser, and the generation appears in history with its complete metadata.

Do **NOT** start:

- LoRA training
- AI caption generation
- Advanced dataset management
- Complex multi-model comparison
- Cloud deployment automation
- Any other later roadmap feature

until Phase 1 is stable.

Complete Phase 1 in this order:

1. Design the architecture.
2. Create the repository structure.
3. Set up Next.js.
4. Set up FastAPI.
5. Set up the database and migrations.
6. Implement system and GPU detection.
7. Implement model discovery.
8. Implement the image-generation service.
9. Connect frontend and backend.
10. Build the Generate page.
11. Save generation history.
12. Implement basic LoRA loading if required for the MVP.
13. Add validation and error handling.
14. Add backend tests.
15. Add frontend tests.
16. Add Playwright E2E tests.
17. Run the full test suite.
18. Fix failures.
19. Manually verify the full generation workflow.
20. Add Docker support.
21. Add GitHub Actions.
22. Complete the README.

## Stop After Phase 1

Do not automatically proceed to Phase 2.

Wait for a new instruction before implementing the next phase.

At the end of Phase 1, report:

- What was implemented
- Files created or modified
- Architecture decisions made
- Commands to run the application
- Commands to run tests
- Test results
- Known limitations
- Any technical debt introduced
- Recommended next milestone