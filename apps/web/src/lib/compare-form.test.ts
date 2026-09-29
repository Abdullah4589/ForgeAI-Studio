import { describe, expect, it } from "vitest";
import {
  buildAxis,
  cellLabel,
  DEFAULT_AXIS_FORM,
  parseSeeds,
  parseStrengths,
  randomSeedList,
  toCompareRequest,
  validateSharedForm,
} from "./compare-form";
import { EMPTY_FORM, type GenerationForm } from "./generation-form";

const form: GenerationForm = {
  ...EMPTY_FORM,
  modelId: "1",
  loraId: "4",
  prompt: " a fox ",
  seed: "77",
};

describe("parseStrengths", () => {
  it("accepts numbers and 'none' as the no-LoRA baseline", () => {
    expect(parseStrengths("none, 0.4, 0.8")).toEqual({ values: [null, 0.4, 0.8] });
    expect(parseStrengths("Off,1,")).toEqual({ values: [null, 1] });
  });

  it.each([
    ["0.5", "Enter between 2 and 6 strengths."],
    ["0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6", "Enter between 2 and 6 strengths."],
    ["0.5, 0.5", "Each strength must be unique."],
    ["none, abc", '"abc" is not a number (use "none" for no LoRA).'],
    ["0, 2.5", "Strengths must be between -2 and 2."],
  ])("rejects %j", (input, error) => {
    expect(parseStrengths(input)).toEqual({ error });
  });
});

describe("parseSeeds", () => {
  it("accepts whole numbers including 0", () => {
    expect(parseSeeds("0, 5,  4294967295")).toEqual({ values: [0, 5, 4294967295] });
  });

  it.each(["1.5, 2", "-1, 2", "4294967296, 1", "x, 1"])("rejects %j", (input) => {
    expect(parseSeeds(input).error).toMatch(/whole numbers/);
  });

  it("generates distinct random seed lists", () => {
    const values = parseSeeds(randomSeedList(3));
    expect(values.values).toHaveLength(3);
  });
});

describe("buildAxis", () => {
  it("builds the chosen axis only", () => {
    expect(buildAxis({ ...DEFAULT_AXIS_FORM, kind: "model", modelIds: ["2", "3"] })).toEqual({
      axis: { kind: "model", values: [2, 3] },
    });
    expect(buildAxis({ ...DEFAULT_AXIS_FORM, kind: "model", modelIds: ["2"] }).error).toBe(
      "Enter between 2 and 6 models.",
    );
  });
});

describe("validateSharedForm", () => {
  it("ignores fields the axis controls", () => {
    const blank = { ...form, modelId: "", seed: "bad" };
    expect(validateSharedForm(blank, "model").modelId).toBeUndefined();
    expect(validateSharedForm(blank, "seed").seed).toBeUndefined();
    expect(validateSharedForm(blank, "lora_strength").modelId).toBe("Select a base model.");
  });

  it("requires a LoRA for a strength comparison", () => {
    expect(validateSharedForm({ ...form, loraId: "" }, "lora_strength").loraId).toMatch(
      /Choose a LoRA/,
    );
  });
});

describe("toCompareRequest", () => {
  it("clears the shared value that the axis supplies", () => {
    const byModel = toCompareRequest(form, { kind: "model", values: [1, 2] });
    expect(byModel).toMatchObject({ model_id: null, seed: 77, prompt: "a fox", lora_id: 4 });
    const bySeed = toCompareRequest(form, { kind: "seed", values: [1, 2] });
    expect(bySeed).toMatchObject({ model_id: 1, seed: null });
    expect(bySeed).not.toHaveProperty("num_images");
  });
});

describe("cellLabel", () => {
  it("labels cells by axis", () => {
    expect(cellLabel("lora_strength", null)).toBe("No LoRA");
    expect(cellLabel("lora_strength", 0.4)).toBe("LoRA 0.40");
    expect(cellLabel("seed", 9)).toBe("Seed 9");
    expect(cellLabel("model", 2, [{ id: 2, name: "tiny sd" }])).toBe("tiny sd");
    expect(cellLabel("model", 3)).toBe("Model #3");
  });
});
