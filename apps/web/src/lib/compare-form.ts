import {
  LIMITS,
  randomSeed,
  toRequest,
  validateForm,
  type FormErrors,
  type GenerationForm,
} from "./generation-form";
import type { CompareAxis, CompareAxisKind, CompareRequest, ModelInfo } from "./types";

// Keep in sync with MIN_CELLS / MAX_CELLS in apps/api/forge_api/schemas/compare.py.
export const MIN_CELLS = 2;
export const MAX_CELLS = 6;

/** Raw editor state for the varying setting; only the field for the chosen axis is used. */
export interface AxisForm {
  kind: CompareAxisKind;
  strengths: string;
  seeds: string;
  modelIds: string[];
}

export const DEFAULT_AXIS_FORM: AxisForm = {
  kind: "lora_strength",
  strengths: "none, 0.5, 1",
  seeds: "",
  modelIds: [],
};

export const AXIS_LABELS: Record<CompareAxisKind, string> = {
  lora_strength: "LoRA strength",
  seed: "Seed",
  model: "Model",
};

const NO_LORA_TOKENS = new Set(["none", "off", "no lora", "no-lora"]);

type Parsed<T> = { values: T[]; error?: undefined } | { values?: undefined; error: string };

function splitList(text: string): string[] {
  return text
    .split(",")
    .map((part) => part.trim())
    .filter(Boolean);
}

function checkCount<T>(values: T[], noun: string): Parsed<T> {
  if (values.length < MIN_CELLS || values.length > MAX_CELLS) {
    return { error: `Enter between ${MIN_CELLS} and ${MAX_CELLS} ${noun}.` };
  }
  if (new Set(values).size !== values.length)
    return { error: `Each ${noun.slice(0, -1)} must be unique.` };
  return { values };
}

export function parseStrengths(text: string): Parsed<number | null> {
  const values: (number | null)[] = [];
  for (const token of splitList(text)) {
    if (NO_LORA_TOKENS.has(token.toLowerCase())) {
      values.push(null);
      continue;
    }
    const value = Number(token);
    if (Number.isNaN(value))
      return { error: `"${token}" is not a number (use "none" for no LoRA).` };
    if (value < LIMITS.loraStrengthMin || value > LIMITS.loraStrengthMax) {
      return {
        error: `Strengths must be between ${LIMITS.loraStrengthMin} and ${LIMITS.loraStrengthMax}.`,
      };
    }
    values.push(value);
  }
  return checkCount(values, "strengths");
}

export function parseSeeds(text: string): Parsed<number> {
  const values: number[] = [];
  for (const token of splitList(text)) {
    if (!/^\d+$/.test(token) || Number(token) > LIMITS.seedMax) {
      return { error: `Seeds must be whole numbers between 0 and ${LIMITS.seedMax}.` };
    }
    values.push(Number(token));
  }
  return checkCount(values, "seeds");
}

export function parseModelIds(ids: string[]): Parsed<number> {
  return checkCount(ids.map(Number), "models");
}

export function buildAxis(form: AxisForm): { axis?: CompareAxis; error?: string } {
  if (form.kind === "lora_strength") {
    const parsed = parseStrengths(form.strengths);
    return parsed.error
      ? { error: parsed.error }
      : { axis: { kind: form.kind, values: parsed.values! } };
  }
  if (form.kind === "seed") {
    const parsed = parseSeeds(form.seeds);
    return parsed.error
      ? { error: parsed.error }
      : { axis: { kind: form.kind, values: parsed.values! } };
  }
  const parsed = parseModelIds(form.modelIds);
  return parsed.error
    ? { error: parsed.error }
    : { axis: { kind: form.kind, values: parsed.values! } };
}

/**
 * Validate the shared settings, ignoring the ones the axis controls (a comparison always makes
 * one image per cell, the model axis supplies the models, and the seed axis supplies the seeds).
 */
export function validateSharedForm(form: GenerationForm, kind: CompareAxisKind): FormErrors {
  const errors = validateForm({ ...form, numImages: "1" });
  if (kind === "model") delete errors.modelId;
  if (kind === "seed") delete errors.seed;
  if (kind === "lora_strength" && !form.loraId)
    errors.loraId = "Choose a LoRA to compare its strengths.";
  return errors;
}

export function toCompareRequest(form: GenerationForm, axis: CompareAxis): CompareRequest {
  const base = toRequest({ ...form, numImages: "1" });
  return {
    axis,
    prompt: base.prompt,
    negative_prompt: base.negative_prompt,
    model_id: axis.kind === "model" ? null : base.model_id,
    lora_id: base.lora_id,
    lora_strength: base.lora_strength,
    width: base.width,
    height: base.height,
    steps: base.steps,
    guidance_scale: base.guidance_scale,
    seed: axis.kind === "seed" ? null : base.seed,
  };
}

export function cellLabel(
  kind: CompareAxisKind,
  value: number | null,
  models: Pick<ModelInfo, "id" | "name">[] = [],
): string {
  if (kind === "lora_strength") return value === null ? "No LoRA" : `LoRA ${value.toFixed(2)}`;
  if (kind === "seed") return `Seed ${value}`;
  return models.find((m) => m.id === value)?.name ?? `Model #${value}`;
}

export function randomSeedList(count = 3): string {
  return Array.from({ length: count }, randomSeed).join(", ");
}
