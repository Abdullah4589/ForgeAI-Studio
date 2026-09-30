import type { TrainingRequest, TrainingRun } from "./types";

// Keep in sync with TrainingRequest in apps/api/forge_api/schemas/training.py.
export const TRAINING_LIMITS = {
  rank: [1, 128],
  alpha: [0.1, 256],
  learningRate: [1e-6, 1e-2],
  batchSize: [1, 8],
  steps: [1, 20_000],
  saveEvery: [0, 20_000],
  sampleCount: [0, 4],
  sampleSteps: [1, 50],
} as const;
export const RESOLUTIONS = [256, 512, 768] as const;

/** Raw form state: numbers as strings so partial typing isn't clobbered. */
export interface TrainingForm {
  datasetId: string;
  baseModelId: string;
  name: string;
  triggerWord: string;
  resolution: string;
  rank: string;
  alpha: string;
  learningRate: string;
  batchSize: string;
  steps: string;
  saveEvery: string;
  seed: string;
  sampleCount: string;
  sampleSteps: string;
}

export type TrainingFormErrors = Partial<Record<keyof TrainingForm, string>>;

type PresetValues = Pick<
  TrainingForm,
  | "resolution"
  | "rank"
  | "alpha"
  | "learningRate"
  | "batchSize"
  | "steps"
  | "saveEvery"
  | "sampleCount"
  | "sampleSteps"
>;

export const PRESETS: { id: string; label: string; hint: string; values: PresetValues }[] = [
  {
    id: "quick",
    label: "Quick test",
    hint: "256 px, 200 steps. Checks the whole pipeline fast; results are rough.",
    values: {
      resolution: "256",
      rank: "8",
      alpha: "8",
      learningRate: "0.0001",
      batchSize: "1",
      steps: "200",
      saveEvery: "50",
      sampleCount: "2",
      sampleSteps: "20",
    },
  },
  {
    id: "standard",
    label: "Standard",
    hint: "512 px, 800 steps. A typical small SD 1.x style or subject LoRA.",
    values: {
      resolution: "512",
      rank: "16",
      alpha: "16",
      learningRate: "0.0001",
      batchSize: "1",
      steps: "800",
      saveEvery: "200",
      sampleCount: "2",
      sampleSteps: "25",
    },
  },
];

export const EMPTY_TRAINING_FORM: TrainingForm = {
  datasetId: "",
  baseModelId: "",
  name: "",
  triggerWord: "",
  seed: "",
  ...PRESETS[0].values,
};

function checkNumber(
  value: string,
  [min, max]: readonly [number, number],
  label: string,
  integer: boolean,
): string | undefined {
  const n = Number(value);
  if (value.trim() === "" || Number.isNaN(n)) return `${label} must be a number.`;
  if (integer && !Number.isInteger(n)) return `${label} must be a whole number.`;
  if (n < min || n > max) return `${label} must be between ${min} and ${max}.`;
  return undefined;
}

export function validateTrainingForm(form: TrainingForm): TrainingFormErrors {
  const errors: TrainingFormErrors = {};
  if (!form.datasetId) errors.datasetId = "Choose a dataset.";
  if (!form.baseModelId) errors.baseModelId = "Choose a base model.";
  if (!form.name.trim()) errors.name = "Name the LoRA.";
  else if (form.name.length > 100) errors.name = "Keep the name under 100 characters.";
  if (form.triggerWord.length > 100) errors.triggerWord = "Keep the trigger word short.";
  const checks: [keyof TrainingForm, readonly [number, number], string, boolean][] = [
    ["rank", TRAINING_LIMITS.rank, "Rank", true],
    ["alpha", TRAINING_LIMITS.alpha, "Alpha", false],
    ["learningRate", TRAINING_LIMITS.learningRate, "Learning rate", false],
    ["batchSize", TRAINING_LIMITS.batchSize, "Batch size", true],
    ["steps", TRAINING_LIMITS.steps, "Steps", true],
    ["saveEvery", TRAINING_LIMITS.saveEvery, "Save interval", true],
    ["sampleCount", TRAINING_LIMITS.sampleCount, "Samples", true],
    ["sampleSteps", TRAINING_LIMITS.sampleSteps, "Sample steps", true],
  ];
  for (const [key, range, label, integer] of checks) {
    const error = checkNumber(form[key], range, label, integer);
    if (error) errors[key] = error;
  }
  if (form.seed.trim() && !/^\d+$/.test(form.seed.trim()))
    errors.seed = "Seed must be a whole number.";
  return errors;
}

export function toTrainingRequest(form: TrainingForm): TrainingRequest {
  return {
    dataset_id: Number(form.datasetId),
    base_model_id: Number(form.baseModelId),
    name: form.name.trim(),
    trigger_word: form.triggerWord.trim(),
    resolution: Number(form.resolution) as TrainingRequest["resolution"],
    rank: Number(form.rank),
    alpha: Number(form.alpha),
    learning_rate: Number(form.learningRate),
    batch_size: Number(form.batchSize),
    steps: Number(form.steps),
    save_every: Number(form.saveEvery),
    seed: form.seed.trim() ? Number(form.seed) : null,
    sample_count: Number(form.sampleCount),
    sample_steps: Number(form.sampleSteps),
  };
}

/**
 * Estimated training time from this machine's own history: the latest finished run's measured
 * seconds per step, scaled by pixel count and batch size. Null until a run has finished.
 */
export function estimateSeconds(runs: TrainingRun[], form: TrainingForm): number | null {
  const reference = runs.find((run) => run.status === "completed" && run.avg_step_seconds);
  const steps = Number(form.steps);
  const resolution = Number(form.resolution);
  const batch = Number(form.batchSize);
  if (!reference?.avg_step_seconds || !steps || !resolution || !batch) return null;
  const scale = (resolution / reference.resolution) ** 2 * (batch / reference.batch_size);
  return reference.avg_step_seconds * scale * steps;
}

export function formatSeconds(seconds: number): string {
  if (seconds < 90) return `${Math.round(seconds)} s`;
  const minutes = Math.round(seconds / 60);
  if (minutes < 90) return `${minutes} min`;
  return `${Math.floor(minutes / 60)} h ${minutes % 60} min`;
}

/** Remaining time for a running job, from its average pace so far. */
export function remainingSeconds(step: number, total: number, elapsedMs: number): number | null {
  if (step <= 0 || step >= total) return null;
  return (elapsedMs / 1000 / step) * (total - step);
}

/** SVG path for a loss curve inside a width x height box (higher loss drawn higher). */
export function lossPath(points: [number, number][], width: number, height: number): string {
  if (points.length < 2) return "";
  const steps = points.map(([step]) => step);
  const losses = points.map(([, loss]) => loss);
  const [minStep, maxStep] = [Math.min(...steps), Math.max(...steps)];
  const [minLoss, maxLoss] = [Math.min(...losses), Math.max(...losses)];
  const x = (step: number) => ((step - minStep) / (maxStep - minStep || 1)) * width;
  const y = (loss: number) => height - ((loss - minLoss) / (maxLoss - minLoss || 1)) * height;
  return points
    .map(([step, loss], i) => `${i === 0 ? "M" : "L"}${x(step).toFixed(1)},${y(loss).toFixed(1)}`)
    .join(" ");
}
