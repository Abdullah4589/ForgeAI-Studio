import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeAll, describe, expect, it, vi } from "vitest";
import type { Generation } from "@/lib/types";
import { GenerationStatus } from "./GenerationStatus";
import { ResultGrid } from "./ResultGrid";

const generation: Generation = {
  id: 3,
  created_at: "2026-01-01T00:00:00Z",
  prompt: "a red fox",
  negative_prompt: "",
  model_id: 1,
  model_name: "tiny sd",
  lora_id: null,
  lora_name: null,
  lora_strength: null,
  seed: 100,
  width: 256,
  height: 256,
  steps: 4,
  guidance_scale: 7.5,
  num_images: 2,
  duration_ms: 1500,
  device: "cpu",
  pipeline_config: { backend: "mock" },
  comparison_id: null,
  comparison_index: null,
  images: [
    {
      id: 11,
      index: 0,
      seed: 100,
      width: 256,
      height: 256,
      file_size_bytes: 10,
      safety_blocked: false,
      url: "/api/images/11",
    },
    {
      id: 12,
      index: 1,
      seed: 101,
      width: 256,
      height: 256,
      file_size_bytes: 10,
      safety_blocked: false,
      url: "/api/images/12",
    },
  ],
};

beforeAll(() => {
  // jsdom doesn't implement <dialog> modality.
  HTMLDialogElement.prototype.showModal = vi.fn();
  HTMLDialogElement.prototype.close = vi.fn();
});

describe("ResultGrid", () => {
  it("renders images with working actions", async () => {
    const onReuse = vi.fn();
    const onCopy = vi.fn();
    const onDelete = vi.fn();
    render(
      <ResultGrid
        generation={generation}
        onReuse={onReuse}
        onCopyPrompt={onCopy}
        onDelete={onDelete}
      />,
    );

    expect(screen.getAllByRole("img")).toHaveLength(2);
    expect(screen.getByRole("link", { name: "Download image 1" })).toHaveAttribute(
      "href",
      "http://localhost:8000/api/images/11?download=true",
    );

    await userEvent.click(screen.getByRole("button", { name: "Reuse settings of image 2" }));
    expect(onReuse).toHaveBeenCalledWith(generation, generation.images[1]);

    await userEvent.click(screen.getAllByRole("button", { name: "Copy prompt" })[0]);
    expect(onCopy).toHaveBeenCalledWith("a red fox");

    await userEvent.click(screen.getByRole("button", { name: "Delete image 1" }));
    expect(onDelete).toHaveBeenCalledWith(generation.images[0]);
  });

  it("shows metadata for an image", async () => {
    render(
      <ResultGrid
        generation={generation}
        onReuse={vi.fn()}
        onCopyPrompt={vi.fn()}
        onDelete={vi.fn()}
      />,
    );
    await userEvent.click(screen.getByRole("button", { name: "View metadata of image 2" }));
    const dialog = screen.getByRole("dialog", { hidden: true });
    expect(dialog).toHaveTextContent("101");
    expect(dialog).toHaveTextContent("tiny sd");
  });
});

describe("ResultGrid safety checker", () => {
  it("explains blocked images instead of showing a black frame", () => {
    const blocked = {
      ...generation,
      images: [{ ...generation.images[0], safety_blocked: true }, generation.images[1]],
    };
    render(
      <ResultGrid
        generation={blocked}
        onReuse={vi.fn()}
        onCopyPrompt={vi.fn()}
        onDelete={vi.fn()}
      />,
    );

    expect(screen.getByRole("img", { name: "Blocked by the safety checker" })).toBeInTheDocument();
    expect(screen.getByText(/Try more steps or a different seed/)).toBeInTheDocument();
    // Nothing useful to download, but the settings can still be reused with another seed.
    expect(screen.queryByRole("link", { name: "Download image 1" })).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Download image 2" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Reuse settings of image 1" })).toBeInTheDocument();
  });
});

describe("GenerationStatus", () => {
  it("shows progress for a running job", () => {
    render(
      <GenerationStatus
        elapsedMs={2500}
        job={{
          id: "j",
          kind: "generation",
          status: "running",
          step: 5,
          total_steps: 20,
          message: "Step 5 of 20",
          created_at: 0,
          started_at: 0,
          finished_at: null,
          result: null,
          error: null,
        }}
      />,
    );
    expect(screen.getByRole("progressbar")).toHaveAttribute("aria-valuenow", "25");
    expect(screen.getByText(/Step 5 of 20/)).toBeInTheDocument();
    expect(screen.getByLabelText("Duration")).toHaveTextContent("2.5 s");
  });
});
