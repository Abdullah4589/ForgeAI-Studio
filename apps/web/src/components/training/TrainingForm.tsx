"use client";

import { GraduationCap } from "lucide-react";
import { Button, FieldError, inputClass, Panel } from "@/components/ui/primitives";
import {
  estimateSeconds,
  formatSeconds,
  PRESETS,
  RESOLUTIONS,
  type TrainingForm as Form,
  type TrainingFormErrors,
} from "@/lib/training";
import type { DatasetSummary, ModelInfo, TrainingRun } from "@/lib/types";

interface TrainingFormProps {
  form: Form;
  errors: TrainingFormErrors;
  datasets: DatasetSummary[];
  models: ModelInfo[];
  runs: TrainingRun[];
  disabled: boolean;
  onChange: (changes: Partial<Form>) => void;
  onSubmit: () => void;
}

/** Only SD 1.x training is supported so far. */
export function trainableModels(models: ModelInfo[]): ModelInfo[] {
  return models.filter((m) => m.available && m.architecture === "sd15");
}

export function TrainingForm({
  form,
  errors,
  datasets,
  models,
  runs,
  disabled,
  onChange,
  onSubmit,
}: TrainingFormProps) {
  const dataset = datasets.find((d) => String(d.id) === form.datasetId);
  const estimate = estimateSeconds(runs, form);
  const field = (key: keyof Form, label: string, props: FieldProps = {}) => (
    <Field
      id={`train-${key}`}
      label={label}
      value={form[key]}
      error={errors[key]}
      onChange={(value) => onChange({ [key]: value })}
      {...props}
    />
  );

  return (
    <Panel title="New training run">
      <form
        noValidate
        onSubmit={(event) => {
          event.preventDefault();
          onSubmit();
        }}
      >
        <fieldset disabled={disabled} className="space-y-4">
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <div>
              <label htmlFor="train-dataset" className="text-muted mb-1 block text-xs font-medium">
                Dataset
              </label>
              <select
                id="train-dataset"
                value={form.datasetId}
                onChange={(event) => onChange({ datasetId: event.target.value })}
                aria-invalid={errors.datasetId ? true : undefined}
                className={inputClass}
              >
                <option value="">Choose a dataset</option>
                {datasets.map((d) => (
                  <option key={d.id} value={d.id}>
                    {d.name} ({d.image_count} images)
                  </option>
                ))}
              </select>
              <FieldError id="train-dataset-error" message={errors.datasetId} />
              {dataset && dataset.uncaptioned_count > 0 && (
                <p className="text-muted mt-1 text-xs">
                  {dataset.uncaptioned_count} image
                  {dataset.uncaptioned_count === 1 ? " has" : "s have"} no caption and will train on
                  the trigger word only.
                </p>
              )}
            </div>
            <div>
              <label htmlFor="train-model" className="text-muted mb-1 block text-xs font-medium">
                Base model
              </label>
              <select
                id="train-model"
                value={form.baseModelId}
                onChange={(event) => onChange({ baseModelId: event.target.value })}
                aria-invalid={errors.baseModelId ? true : undefined}
                className={inputClass}
              >
                <option value="">Choose a model</option>
                {trainableModels(models).map((m) => (
                  <option key={m.id} value={m.id}>
                    {m.name}
                  </option>
                ))}
              </select>
              <FieldError id="train-model-error" message={errors.baseModelId} />
              <p className="text-faint mt-1 text-xs">Stable Diffusion 1.x models only for now.</p>
            </div>
            {field("name", "LoRA name", { placeholder: "my-style" })}
            {field("triggerWord", "Trigger word", { placeholder: "e.g. fgx style" })}
          </div>

          <div>
            <p className="text-muted mb-2 text-xs font-medium">Preset</p>
            <div className="flex flex-wrap gap-2">
              {PRESETS.map((preset) => (
                <Button key={preset.id} onClick={() => onChange(preset.values)} title={preset.hint}>
                  {preset.label}
                </Button>
              ))}
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            <div>
              <label
                htmlFor="train-resolution"
                className="text-muted mb-1 block text-xs font-medium"
              >
                Resolution
              </label>
              <select
                id="train-resolution"
                value={form.resolution}
                onChange={(event) => onChange({ resolution: event.target.value })}
                className={inputClass}
              >
                {RESOLUTIONS.map((r) => (
                  <option key={r} value={r}>
                    {r} px
                  </option>
                ))}
              </select>
            </div>
            {field("steps", "Training steps", { numeric: true })}
            {field("rank", "Rank", { numeric: true })}
            {field("alpha", "Alpha", { numeric: true })}
            {field("learningRate", "Learning rate", { numeric: true })}
            {field("batchSize", "Batch size", { numeric: true })}
            {field("saveEvery", "Save every (steps)", { numeric: true })}
            {field("seed", "Seed", { numeric: true, placeholder: "Random" })}
            {field("sampleCount", "Samples", { numeric: true })}
            {field("sampleSteps", "Sample steps", { numeric: true })}
          </div>

          <div className="flex flex-wrap items-center gap-3">
            <Button type="submit" variant="primary">
              <GraduationCap aria-hidden className="size-4" />
              Start training
            </Button>
            <p className="text-muted text-xs" aria-live="polite">
              {estimate === null
                ? "A time estimate appears after your first finished run on this machine."
                : `Estimated ~${formatSeconds(estimate)} of training on this machine, plus samples.`}
            </p>
          </div>
        </fieldset>
      </form>
    </Panel>
  );
}

interface FieldProps {
  placeholder?: string;
  numeric?: boolean;
}

function Field({
  id,
  label,
  value,
  error,
  onChange,
  placeholder,
  numeric,
}: FieldProps & {
  id: string;
  label: string;
  value: string;
  error?: string;
  onChange: (value: string) => void;
}) {
  return (
    <div>
      <label htmlFor={id} className="text-muted mb-1 block text-xs font-medium">
        {label}
      </label>
      <input
        id={id}
        value={value}
        placeholder={placeholder}
        inputMode={numeric ? "decimal" : undefined}
        aria-invalid={error ? true : undefined}
        aria-describedby={error ? `${id}-error` : undefined}
        onChange={(event) => onChange(event.target.value)}
        className={`${inputClass} ${numeric ? "font-mono" : ""}`}
      />
      <FieldError id={`${id}-error`} message={error} />
    </div>
  );
}
