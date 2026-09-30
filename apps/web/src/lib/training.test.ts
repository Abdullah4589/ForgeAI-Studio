import { describe, expect, it } from "vitest";
import {
  EMPTY_TRAINING_FORM,
  estimateSeconds,
  formatSeconds,
  lossPath,
  PRESETS,
  remainingSeconds,
  toTrainingRequest,
  validateTrainingForm,
  type TrainingForm,
} from "./training";
import type { TrainingRun } from "./types";

const valid: TrainingForm = {
  ...EMPTY_TRAINING_FORM,
  datasetId: "1",
  baseModelId: "2",
  name: "my-style",
  triggerWord: "fgx",
};

describe("validateTrainingForm", () => {
  it("accepts a valid form", () => {
    expect(validateTrainingForm(valid)).toEqual({});
  });

  it("requires dataset, model and name", () => {
    const errors = validateTrainingForm({ ...valid, datasetId: "", baseModelId: "", name: " " });
    expect(errors).toMatchObject({
      datasetId: "Choose a dataset.",
      baseModelId: "Choose a base model.",
      name: "Name the LoRA.",
    });
  });

  it.each([
    ["rank", "0", "Rank must be between 1 and 128."],
    ["rank", "4.5", "Rank must be a whole number."],
    ["learningRate", "0.5", "Learning rate must be between 0.000001 and 0.01."],
    ["steps", "abc", "Steps must be a number."],
    ["batchSize", "9", "Batch size must be between 1 and 8."],
    ["seed", "-1", "Seed must be a whole number."],
  ] as const)("rejects %s=%s", (field, value, message) => {
    expect(validateTrainingForm({ ...valid, [field]: value })[field]).toBe(message);
  });
});

it("builds a request from the form", () => {
  expect(toTrainingRequest({ ...valid, seed: "", learningRate: "0.0002" })).toMatchObject({
    dataset_id: 1,
    base_model_id: 2,
    name: "my-style",
    trigger_word: "fgx",
    resolution: 256,
    learning_rate: 0.0002,
    seed: null,
  });
});

it("presets fill valid settings", () => {
  for (const preset of PRESETS) {
    expect(validateTrainingForm({ ...valid, ...preset.values })).toEqual({});
  }
});

describe("estimateSeconds", () => {
  const finished = {
    status: "completed",
    avg_step_seconds: 3,
    resolution: 256,
    batch_size: 1,
  } as TrainingRun;

  it("has no estimate before any finished run", () => {
    expect(estimateSeconds([], valid)).toBeNull();
    expect(estimateSeconds([{ ...finished, status: "failed" }], valid)).toBeNull();
  });

  it("scales the measured pace by pixels, batch size and steps", () => {
    expect(estimateSeconds([finished], { ...valid, resolution: "256", steps: "100" })).toBe(300);
    expect(
      estimateSeconds([finished], { ...valid, resolution: "512", batchSize: "2", steps: "100" }),
    ).toBe(3 * 4 * 2 * 100);
  });
});

it("formats durations and remaining time", () => {
  expect(formatSeconds(45)).toBe("45 s");
  expect(formatSeconds(600)).toBe("10 min");
  expect(formatSeconds(3 * 3600 + 20 * 60)).toBe("3 h 20 min");
  expect(remainingSeconds(10, 100, 20_000)).toBe(180);
  expect(remainingSeconds(0, 100, 0)).toBeNull();
});

it("draws the loss path inside the box", () => {
  expect(lossPath([[1, 0.5]], 100, 50)).toBe("");
  expect(
    lossPath(
      [
        [1, 1],
        [2, 0],
      ],
      100,
      50,
    ),
  ).toBe("M0.0,0.0 L100.0,50.0");
});
