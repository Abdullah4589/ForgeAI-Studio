// Starts the FastAPI backend in mock-generation mode against a fresh, throwaway storage folder
// so every Playwright run begins from a known state. Used by playwright.config.ts.
import { spawn } from "node:child_process";
import { existsSync, mkdirSync, rmSync, writeFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const repoRoot = resolve(here, "../../..");
const storage = join(here, ".e2e-storage");
const port = process.env.E2E_API_PORT ?? "8001";
const webPort = process.env.E2E_WEB_PORT ?? "3100";

rmSync(storage, { recursive: true, force: true });
// Diffusers-style folders are enough for discovery; the mock backend never loads weights.
// Two models so comparison tests can vary the model.
for (const name of ["tiny-sd", "tiny-sd-b"]) {
  const modelDir = join(storage, "models", name);
  mkdirSync(modelDir, { recursive: true });
  writeFileSync(
    join(modelDir, "model_index.json"),
    JSON.stringify({ _class_name: "StableDiffusionPipeline" }),
  );
}

const venvPython =
  process.platform === "win32"
    ? join(repoRoot, ".venv", "Scripts", "python.exe")
    : join(repoRoot, ".venv", "bin", "python");
const python = process.env.PYTHON ?? (existsSync(venvPython) ? venvPython : "python");

const child = spawn(
  python,
  ["-m", "uvicorn", "forge_api.main:app", "--app-dir", "apps/api", "--port", port],
  {
    cwd: repoRoot,
    stdio: "inherit",
    env: {
      ...process.env,
      GENERATION_BACKEND: "mock",
      MOCK_STEP_DELAY_SECONDS: "0.02",
      DATABASE_URL: `sqlite:///${join(storage, "e2e.db").replaceAll("\\", "/")}`,
      MODEL_DIRECTORY: join(storage, "models"),
      LORA_DIRECTORY: join(storage, "loras"),
      OUTPUT_DIRECTORY: join(storage, "outputs"),
      CORS_ORIGINS: `http://localhost:${webPort},http://127.0.0.1:${webPort}`,
      LOG_LEVEL: "WARNING",
    },
  },
);

for (const signal of ["SIGINT", "SIGTERM"]) {
  process.on(signal, () => child.kill(signal));
}
child.on("exit", (code) => process.exit(code ?? 0));
