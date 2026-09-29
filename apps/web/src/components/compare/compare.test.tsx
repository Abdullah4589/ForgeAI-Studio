import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { DEFAULT_AXIS_FORM } from "@/lib/compare-form";
import type { Comparison, Generation, ModelInfo } from "@/lib/types";
import { AxisPanel } from "./AxisPanel";
import { ComparisonResults } from "./ComparisonResults";

function model(id: number, name: string, architecture = "sd15"): ModelInfo {
  return {
    id,
    name,
    path: name,
    source_type: "diffusers",
    architecture,
    file_size_bytes: 1,
    description: "",
    preview_image_path: null,
    supported_resolutions: [],
    available: true,
    loaded: false,
    created_at: "2026-01-01T00:00:00Z",
  };
}

function cell(index: number, overrides: Partial<Generation> = {}): Generation {
  return {
    id: 100 + index,
    created_at: "2026-01-01T00:00:00Z",
    prompt: "a fox",
    negative_prompt: "",
    model_id: 1,
    model_name: "tiny sd",
    lora_id: 4,
    lora_name: "style",
    lora_strength: 0.4,
    seed: 42,
    width: 256,
    height: 256,
    steps: 5,
    guidance_scale: 7.5,
    num_images: 1,
    duration_ms: 1200,
    device: "cpu",
    pipeline_config: {},
    comparison_id: 1,
    comparison_index: index,
    images: [
      {
        id: 200 + index,
        index: 0,
        seed: 42,
        width: 256,
        height: 256,
        file_size_bytes: 1,
        safety_blocked: false,
        url: `/api/images/${200 + index}`,
      },
    ],
    ...overrides,
  };
}

describe("AxisPanel", () => {
  it("switches between axis editors", async () => {
    const onChange = vi.fn();
    const { rerender } = render(
      <AxisPanel axis={DEFAULT_AXIS_FORM} models={[]} onChange={onChange} />,
    );
    expect(screen.getByLabelText("Strengths")).toHaveValue("none, 0.5, 1");

    await userEvent.selectOptions(screen.getByLabelText("Vary"), "seed");
    expect(onChange).toHaveBeenLastCalledWith({ ...DEFAULT_AXIS_FORM, kind: "seed" });

    rerender(
      <AxisPanel axis={{ ...DEFAULT_AXIS_FORM, kind: "seed" }} models={[]} onChange={onChange} />,
    );
    await userEvent.click(screen.getByRole("button", { name: "Random seeds" }));
    expect(onChange.mock.lastCall?.[0].seeds.split(",")).toHaveLength(3);
  });

  it("lists only usable models as checkboxes", async () => {
    const onChange = vi.fn();
    render(
      <AxisPanel
        axis={{ ...DEFAULT_AXIS_FORM, kind: "model", modelIds: ["1"] }}
        models={[model(1, "tiny sd"), model(2, "xl", "sdxl"), model(3, "odd", "unknown")]}
        error="Enter between 2 and 6 models."
        onChange={onChange}
      />,
    );
    expect(screen.getByRole("checkbox", { name: /tiny sd/ })).toBeChecked();
    expect(screen.queryByRole("checkbox", { name: /odd/ })).not.toBeInTheDocument();
    expect(screen.getByText("Enter between 2 and 6 models.")).toBeInTheDocument();

    await userEvent.click(screen.getByRole("checkbox", { name: /xl/ }));
    expect(onChange).toHaveBeenCalledWith(expect.objectContaining({ modelIds: ["1", "2"] }));
  });
});

describe("ComparisonResults", () => {
  const comparison: Comparison = {
    id: 1,
    created_at: "2026-01-01T00:00:00Z",
    prompt: "a fox",
    axis: "lora_strength",
    axis_values: [null, 0.4, 0.8],
    status: "cancelled",
    error_message: null,
    cells: [cell(0, { lora_id: null, lora_name: null, lora_strength: null }), cell(1)],
  };

  it("shows each axis value side by side, with a placeholder for missing cells", () => {
    render(<ComparisonResults comparison={comparison} models={[]} onDelete={vi.fn()} />);
    const cells = within(screen.getByRole("list", { name: "Comparison cells" })).getAllByRole(
      "listitem",
    );
    expect(cells.map((c) => c.getAttribute("aria-label"))).toEqual([
      "No LoRA",
      "LoRA 0.40",
      "LoRA 0.80",
    ]);
    expect(within(cells[0]).getByRole("img")).toHaveAttribute(
      "src",
      "http://localhost:8000/api/images/200",
    );
    expect(within(cells[1]).getByText("style @ 0.40")).toBeInTheDocument();
    expect(within(cells[2]).getByText("Not generated")).toBeInTheDocument();
    expect(
      within(cells[1]).getByRole("link", { name: "Reuse settings of LoRA 0.40" }),
    ).toHaveAttribute("href", "/generate?from=101");
    expect(screen.getByText("cancelled")).toBeInTheDocument();
  });

  it("asks for confirmation before deleting", async () => {
    const onDelete = vi.fn();
    render(<ComparisonResults comparison={comparison} models={[]} onDelete={onDelete} />);
    await userEvent.click(screen.getByRole("button", { name: "Delete comparison" }));
    expect(onDelete).not.toHaveBeenCalled();
    await userEvent.click(screen.getByRole("button", { name: "Confirm delete" }));
    expect(onDelete).toHaveBeenCalledWith(comparison);
  });
});
