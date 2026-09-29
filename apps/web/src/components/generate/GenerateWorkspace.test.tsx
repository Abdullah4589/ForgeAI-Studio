import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { AppSettings, ModelInfo } from "@/lib/types";
import { GenerateWorkspace } from "./GenerateWorkspace";

const { api } = vi.hoisted(() => ({
  api: {
    listModels: vi.fn(),
    listLoras: vi.fn(),
    getSettings: vi.fn(),
    getGeneration: vi.fn(),
    generate: vi.fn(),
  },
}));

vi.mock("@/lib/api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/api")>()),
  api,
}));

const model: ModelInfo = {
  id: 5,
  name: "tiny sd",
  path: "tiny-sd",
  source_type: "diffusers",
  architecture: "sd15",
  file_size_bytes: 1,
  description: "",
  preview_image_path: null,
  supported_resolutions: [[512, 512]],
  available: true,
  loaded: false,
  created_at: "2026-01-01T00:00:00Z",
};

const settings = {
  runtime: {},
  generation_defaults: {
    negative_prompt: "blurry",
    width: 768,
    height: 768,
    steps: 30,
    guidance_scale: 6,
    num_images: 2,
  },
} as unknown as AppSettings;

function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((r) => (resolve = r));
  return { promise, resolve };
}

describe("GenerateWorkspace initial load", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    api.listLoras.mockResolvedValue([]);
    api.getSettings.mockResolvedValue(settings);
  });

  it("applies saved defaults and preselects a model", async () => {
    api.listModels.mockResolvedValue([model]);
    render(<GenerateWorkspace fromGenerationId={null} autoRun={false} />);

    await waitFor(() => expect(screen.getByLabelText("Base model")).toHaveValue("5"));
    expect(screen.getByLabelText("Width")).toHaveValue(768);
    expect(screen.getByLabelText("Negative prompt")).toHaveValue("blurry");
  });

  it("keeps what the user typed if the initial fetch resolves late", async () => {
    const models = deferred<ModelInfo[]>();
    api.listModels.mockReturnValue(models.promise);
    render(<GenerateWorkspace fromGenerationId={null} autoRun={false} />);

    await userEvent.type(screen.getByLabelText("Prompt"), "early bird");
    await act(async () => models.resolve([model]));

    await waitFor(() => expect(screen.getByLabelText("Base model")).toHaveValue("5"));
    expect(screen.getByLabelText("Prompt")).toHaveValue("early bird");
  });
});
