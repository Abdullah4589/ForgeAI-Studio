import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { EMPTY_FORM } from "@/lib/generation-form";
import type { LoraInfo, ModelInfo } from "@/lib/types";
import { compatibleLoras, ModelPanel } from "./ModelPanel";
import { PromptPanel } from "./PromptPanel";
import { SettingsPanel } from "./SettingsPanel";

function model(overrides: Partial<ModelInfo>): ModelInfo {
  return {
    id: 1,
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
    ...overrides,
  };
}

function lora(overrides: Partial<LoraInfo>): LoraInfo {
  return {
    id: 1,
    name: "style",
    filename: "style.safetensors",
    file_size_bytes: 1,
    base_architecture: "sd15",
    rank: 4,
    enabled: true,
    default_strength: 0.8,
    trigger_words: "",
    description: "",
    preview_image_path: null,
    available: true,
    created_at: "2026-01-01T00:00:00Z",
    ...overrides,
  };
}

describe("PromptPanel", () => {
  it("shows character counts and clears the prompt", async () => {
    const onChange = vi.fn();
    render(<PromptPanel prompt="hello" negativePrompt="" errors={{}} onChange={onChange} />);

    expect(screen.getByText("5/2000")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Clear negative prompt" })).toBeDisabled();

    await userEvent.click(screen.getByRole("button", { name: "Clear prompt" }));
    expect(onChange).toHaveBeenCalledWith("prompt", "");
  });

  it("reports typing and shows validation errors", async () => {
    const onChange = vi.fn();
    render(
      <PromptPanel
        prompt=""
        negativePrompt=""
        errors={{ prompt: "Enter a prompt." }}
        onChange={onChange}
      />,
    );
    const textbox = screen.getByLabelText("Prompt");
    expect(textbox).toHaveAttribute("aria-invalid", "true");
    expect(screen.getByText("Enter a prompt.")).toBeInTheDocument();

    await userEvent.type(textbox, "a");
    expect(onChange).toHaveBeenCalledWith("prompt", "a");
  });
});

describe("ModelPanel", () => {
  it("hides unusable models and incompatible or disabled LoRAs", () => {
    const models = [
      model({ id: 1, name: "tiny sd" }),
      model({ id: 2, name: "mystery", architecture: "unknown" }),
      model({ id: 3, name: "gone", available: false }),
    ];
    const loras = [
      lora({ id: 1, name: "sd style" }),
      lora({ id: 2, name: "xl style", base_architecture: "sdxl" }),
      lora({ id: 3, name: "off", enabled: false }),
      lora({ id: 4, name: "generic", base_architecture: "unknown" }),
    ];
    render(
      <ModelPanel
        form={{ ...EMPTY_FORM, modelId: "1" }}
        errors={{}}
        models={models}
        loras={loras}
        onChange={vi.fn()}
      />,
    );

    const modelOptions = screen.getAllByRole("option").map((o) => o.textContent);
    expect(modelOptions).toContain("tiny sd (SD 1.x)");
    expect(modelOptions).not.toContain("mystery (Unknown)");
    expect(modelOptions.some((o) => o?.startsWith("gone"))).toBe(false);
    expect(modelOptions).toEqual(expect.arrayContaining(["None", "sd style", "generic"]));
    expect(modelOptions).not.toContain("xl style");
    expect(modelOptions).not.toContain("off");
    expect(screen.getByLabelText("LoRA strength")).toBeDisabled();
  });

  it("applies the LoRA default strength when a LoRA is chosen", async () => {
    const onChange = vi.fn();
    render(
      <ModelPanel
        form={{ ...EMPTY_FORM, modelId: "1" }}
        errors={{}}
        models={[model({})]}
        loras={[lora({ id: 9, default_strength: 0.6 })]}
        onChange={onChange}
      />,
    );
    await userEvent.selectOptions(screen.getByLabelText("LoRA"), "9");
    expect(onChange).toHaveBeenCalledWith("loraId", "9");
    expect(onChange).toHaveBeenCalledWith("loraStrength", 0.6);
  });

  it("returns no LoRAs without a model", () => {
    expect(compatibleLoras([lora({})], undefined)).toEqual([]);
  });
});

describe("SettingsPanel", () => {
  it("fills a random seed", async () => {
    const onChange = vi.fn();
    render(<SettingsPanel form={EMPTY_FORM} errors={{}} onChange={onChange} />);
    await userEvent.click(screen.getByRole("button", { name: "Random seed" }));
    const [field, value] = onChange.mock.calls[0];
    expect(field).toBe("seed");
    expect(Number(value)).toBeGreaterThanOrEqual(0);
    expect(Number(value)).toBeLessThan(2 ** 32);
  });

  it("shows field errors", () => {
    render(
      <SettingsPanel
        form={EMPTY_FORM}
        errors={{ width: "Width must be a multiple of 8." }}
        onChange={vi.fn()}
      />,
    );
    expect(screen.getByLabelText("Width")).toHaveAttribute("aria-invalid", "true");
    expect(screen.getByText("Width must be a multiple of 8.")).toBeInTheDocument();
  });
});
