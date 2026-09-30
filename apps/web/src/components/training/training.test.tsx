import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { EMPTY_TRAINING_FORM } from "@/lib/training";
import type { DatasetSummary, ModelInfo, TrainingRun } from "@/lib/types";
import { RunList } from "./RunList";
import { TrainingForm, trainableModels } from "./TrainingForm";

const dataset = {
  id: 1,
  name: "Lighthouses",
  image_count: 5,
  uncaptioned_count: 2,
} as DatasetSummary;

function model(id: number, architecture: string, available = true): ModelInfo {
  return { id, name: `model-${id}`, architecture, available } as ModelInfo;
}

const run = {
  id: 7,
  name: "my-style",
  status: "completed",
  dataset_name: "Lighthouses",
  base_model_name: "tiny sd",
  resolution: 256,
  batch_size: 1,
  steps: 200,
  rank: 8,
  trigger_word: "fgx",
  created_at: "2026-01-01T00:00:00Z",
  started_at: "2026-01-01T00:00:00Z",
  finished_at: "2026-01-01T00:10:00Z",
  avg_step_seconds: 3.1,
  current_step: 200,
  error_message: null,
  has_checkpoint: false,
  lora_id: 3,
  loss_history: [
    [1, 0.2],
    [2, 0.1],
  ],
  samples: [
    { index: 0, safety_blocked: false },
    { index: 1, safety_blocked: true },
  ],
  sample_urls: ["/api/training/7/samples/0", "/api/training/7/samples/1"],
} as TrainingRun;

describe("TrainingForm", () => {
  it("only offers SD 1.x models", () => {
    expect(
      trainableModels([model(1, "sd15"), model(2, "sdxl"), model(3, "sd15", false)]).map(
        (m) => m.id,
      ),
    ).toEqual([1]);
  });

  it("warns about uncaptioned images and applies presets", async () => {
    const onChange = vi.fn();
    render(
      <TrainingForm
        form={{ ...EMPTY_TRAINING_FORM, datasetId: "1" }}
        errors={{}}
        datasets={[dataset]}
        models={[model(1, "sd15")]}
        runs={[]}
        disabled={false}
        onChange={onChange}
        onSubmit={vi.fn()}
      />,
    );
    expect(screen.getByText(/2 images have no caption/)).toBeInTheDocument();
    expect(screen.getByText(/A time estimate appears after/)).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "Standard" }));
    expect(onChange).toHaveBeenCalledWith(expect.objectContaining({ resolution: "512" }));
  });

  it("shows an estimate from past runs", () => {
    render(
      <TrainingForm
        form={{ ...EMPTY_TRAINING_FORM, resolution: "256", steps: "200", batchSize: "1" }}
        errors={{ name: "Name the LoRA." }}
        datasets={[dataset]}
        models={[]}
        runs={[run]}
        disabled={false}
        onChange={vi.fn()}
        onSubmit={vi.fn()}
      />,
    );
    expect(screen.getByText(/Estimated ~10 min of training/)).toBeInTheDocument();
    expect(screen.getByLabelText("LoRA name")).toHaveAttribute("aria-invalid", "true");
  });
});

describe("RunList", () => {
  it("shows results, samples and a blocked sample", () => {
    render(<RunList runs={[run]} onDelete={vi.fn()} />);
    const card = within(screen.getByRole("listitem", { name: "Training run my-style" }));
    expect(card.getByText("completed")).toBeInTheDocument();
    expect(card.getByRole("link", { name: "View LoRA" })).toHaveAttribute("href", "/loras");
    expect(card.getByRole("img", { name: "Sample 1 from my-style" })).toBeInTheDocument();
    expect(card.getByRole("img", { name: "Blocked by the safety checker" })).toBeInTheDocument();
    expect(card.getByRole("figure", { name: "Training loss chart" })).toBeInTheDocument();
  });

  it("confirms before deleting", async () => {
    const onDelete = vi.fn();
    render(<RunList runs={[run]} onDelete={onDelete} />);
    await userEvent.click(screen.getByRole("button", { name: "Delete run my-style" }));
    await userEvent.click(screen.getByRole("button", { name: "Delete run" }));
    expect(onDelete).toHaveBeenCalledWith(run);
  });

  it("cannot delete a running run", () => {
    render(<RunList runs={[{ ...run, status: "running" }]} onDelete={vi.fn()} />);
    expect(screen.getByRole("button", { name: "Delete run my-style" })).toBeDisabled();
  });
});
