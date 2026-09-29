import type { Generation, GenerationDefaults, GenerateRequest } from "./types";

// Keep in sync with the limits in apps/api/forge_api/schemas/generation.py.
export const LIMITS = {
  promptMax: 2000,
  sizeMin: 256,
  sizeMax: 1536,
  stepsMin: 1,
  stepsMax: 150,
  guidanceMin: 0,
  guidanceMax: 30,
  imagesMin: 1,
  imagesMax: 4,
  seedMax: 2 ** 32 - 1,
  loraStrengthMin: -2,
  loraStrengthMax: 2,
} as const;

/** Form state keeps raw strings for numeric inputs so partial typing never gets clobbered. */
export interface GenerationForm {
  modelId: string;
  loraId: string;
  loraStrength: number;
  prompt: string;
  negativePrompt: string;
  width: string;
  height: string;
  steps: string;
  guidanceScale: string;
  /** Empty string means "pick a random seed". */
  seed: string;
  numImages: string;
}

export type FormErrors = Partial<Record<keyof GenerationForm, string>>;

export const EMPTY_FORM: GenerationForm = {
  modelId: "",
  loraId: "",
  loraStrength: 1,
  prompt: "",
  negativePrompt: "",
  width: "512",
  height: "512",
  steps: "25",
  guidanceScale: "7.5",
  seed: "",
  numImages: "1",
};

export function formFromDefaults(
  form: GenerationForm,
  defaults: GenerationDefaults,
): GenerationForm {
  return {
    ...form,
    negativePrompt: defaults.negative_prompt,
    width: String(defaults.width),
    height: String(defaults.height),
    steps: String(defaults.steps),
    guidanceScale: String(defaults.guidance_scale),
    numImages: String(defaults.num_images),
  };
}

/** Restore every setting of a past generation. `seed` overrides it, e.g. for one image of a batch. */
export function formFromGeneration(generation: Generation, seed = generation.seed): GenerationForm {
  return {
    modelId: generation.model_id === null ? "" : String(generation.model_id),
    loraId: generation.lora_id === null ? "" : String(generation.lora_id),
    loraStrength: generation.lora_strength ?? 1,
    prompt: generation.prompt,
    negativePrompt: generation.negative_prompt,
    width: String(generation.width),
    height: String(generation.height),
    steps: String(generation.steps),
    guidanceScale: String(generation.guidance_scale),
    seed: String(seed),
    numImages: String(generation.num_images),
  };
}

function checkInteger(value: string, min: number, max: number, label: string): string | undefined {
  if (!/^\d+$/.test(value.trim())) return `${label} must be a whole number.`;
  const n = Number(value);
  if (n < min || n > max) return `${label} must be between ${min} and ${max}.`;
  return undefined;
}

export function validateForm(form: GenerationForm): FormErrors {
  const errors: FormErrors = {};
  if (!form.modelId) errors.modelId = "Select a base model.";
  if (!form.prompt.trim()) errors.prompt = "Enter a prompt.";
  else if (form.prompt.length > LIMITS.promptMax)
    errors.prompt = `Prompt must be at most ${LIMITS.promptMax} characters.`;
  if (form.negativePrompt.length > LIMITS.promptMax)
    errors.negativePrompt = `Negative prompt must be at most ${LIMITS.promptMax} characters.`;

  for (const key of ["width", "height"] as const) {
    const label = key === "width" ? "Width" : "Height";
    const error = checkInteger(form[key], LIMITS.sizeMin, LIMITS.sizeMax, label);
    if (error) errors[key] = error;
    else if (Number(form[key]) % 8 !== 0) errors[key] = `${label} must be a multiple of 8.`;
  }
  const stepsError = checkInteger(form.steps, LIMITS.stepsMin, LIMITS.stepsMax, "Steps");
  if (stepsError) errors.steps = stepsError;

  const guidance = Number(form.guidanceScale);
  if (form.guidanceScale.trim() === "" || Number.isNaN(guidance))
    errors.guidanceScale = "Guidance scale must be a number.";
  else if (guidance < LIMITS.guidanceMin || guidance > LIMITS.guidanceMax)
    errors.guidanceScale = `Guidance scale must be between ${LIMITS.guidanceMin} and ${LIMITS.guidanceMax}.`;

  if (form.seed.trim() !== "") {
    const seedError = checkInteger(form.seed, 0, LIMITS.seedMax, "Seed");
    if (seedError) errors.seed = seedError;
  }
  const imagesError = checkInteger(form.numImages, LIMITS.imagesMin, LIMITS.imagesMax, "Images");
  if (imagesError) errors.numImages = imagesError;
  return errors;
}

export function toRequest(form: GenerationForm): GenerateRequest {
  return {
    model_id: Number(form.modelId),
    prompt: form.prompt.trim(),
    negative_prompt: form.negativePrompt.trim(),
    lora_id: form.loraId ? Number(form.loraId) : null,
    lora_strength: form.loraStrength,
    width: Number(form.width),
    height: Number(form.height),
    steps: Number(form.steps),
    guidance_scale: Number(form.guidanceScale),
    seed: form.seed.trim() === "" ? null : Number(form.seed),
    num_images: Number(form.numImages),
  };
}

const API_FIELD_TO_FORM: Record<string, keyof GenerationForm> = {
  model_id: "modelId",
  lora_id: "loraId",
  lora_strength: "loraStrength",
  prompt: "prompt",
  negative_prompt: "negativePrompt",
  width: "width",
  height: "height",
  steps: "steps",
  guidance_scale: "guidanceScale",
  seed: "seed",
  num_images: "numImages",
};

export function formErrorsFromApi(fields: { field: string; message: string }[]): FormErrors {
  const errors: FormErrors = {};
  for (const { field, message } of fields) {
    const key = API_FIELD_TO_FORM[field];
    if (key) errors[key] = message;
  }
  return errors;
}

export function randomSeed(): string {
  const buffer = new Uint32Array(1);
  crypto.getRandomValues(buffer);
  return String(buffer[0]);
}
