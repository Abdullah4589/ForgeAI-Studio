import { describe, expect, it } from "vitest";
import {
  EMPTY_FORM,
  formErrorsFromApi,
  formFromGeneration,
  toRequest,
  validateForm,
  type GenerationForm,
} from "./generation-form";
import type { Generation } from "./types";

const valid: GenerationForm = { ...EMPTY_FORM, modelId: "1", prompt: "a fox" };

describe("validateForm", () => {
  it("accepts a valid form", () => {
    expect(validateForm(valid)).toEqual({});
  });

  it("requires a model and a non-blank prompt", () => {
    const errors = validateForm({ ...valid, modelId: "", prompt: "   " });
    expect(errors.modelId).toBe("Select a base model.");
    expect(errors.prompt).toBe("Enter a prompt.");
  });

  it.each([
    ["width", "500", "Width must be a multiple of 8."],
    ["width", "128", "Width must be between 256 and 1536."],
    ["height", "abc", "Height must be a whole number."],
    ["steps", "0", "Steps must be between 1 and 150."],
    ["guidanceScale", "31", "Guidance scale must be between 0 and 30."],
    ["guidanceScale", "", "Guidance scale must be a number."],
    ["seed", "-5", "Seed must be a whole number."],
    ["seed", "4294967296", "Seed must be between 0 and 4294967295."],
    ["numImages", "5", "Images must be between 1 and 4."],
  ] as const)("rejects %s=%s", (field, value, message) => {
    expect(validateForm({ ...valid, [field]: value })[field]).toBe(message);
  });

  it("allows an empty seed (random)", () => {
    expect(validateForm({ ...valid, seed: "" }).seed).toBeUndefined();
  });

  it("limits prompt length", () => {
    expect(validateForm({ ...valid, prompt: "x".repeat(2001) }).prompt).toMatch(/at most 2000/);
  });
});

describe("toRequest", () => {
  it("converts strings to typed request values", () => {
    const request = toRequest({ ...valid, prompt: "  a fox  ", seed: "", loraId: "3" });
    expect(request).toMatchObject({
      model_id: 1,
      prompt: "a fox",
      lora_id: 3,
      width: 512,
      guidance_scale: 7.5,
      seed: null,
      num_images: 1,
    });
  });
});

describe("formFromGeneration", () => {
  const generation: Generation = {
    id: 7,
    created_at: "2026-01-01T00:00:00Z",
    prompt: "castle",
    negative_prompt: "blurry",
    model_id: 2,
    model_name: "tiny",
    lora_id: null,
    lora_name: null,
    lora_strength: null,
    seed: 42,
    width: 768,
    height: 512,
    steps: 30,
    guidance_scale: 6,
    num_images: 2,
    duration_ms: 1000,
    device: "cpu",
    pipeline_config: {},
    images: [],
  };

  it("restores every setting", () => {
    expect(formFromGeneration(generation)).toEqual({
      modelId: "2",
      loraId: "",
      loraStrength: 1,
      prompt: "castle",
      negativePrompt: "blurry",
      width: "768",
      height: "512",
      steps: "30",
      guidanceScale: "6",
      seed: "42",
      numImages: "2",
    });
  });

  it("can override the seed for a single image", () => {
    expect(formFromGeneration(generation, 43).seed).toBe("43");
  });
});

it("maps API field errors onto form fields", () => {
  expect(
    formErrorsFromApi([
      { field: "guidance_scale", message: "too big" },
      { field: "unknown", message: "ignored" },
    ]),
  ).toEqual({ guidanceScale: "too big" });
});
