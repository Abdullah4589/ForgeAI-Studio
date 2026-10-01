import Link from "next/link";
import { FieldError, inputClass, Panel } from "@/components/ui/primitives";
import { architectureLabel } from "@/lib/format";
import { LIMITS, type FormErrors, type GenerationForm } from "@/lib/generation-form";
import type { LoraInfo, ModelInfo } from "@/lib/types";

interface ModelPanelProps {
  form: GenerationForm;
  errors: FormErrors;
  models: ModelInfo[];
  loras: LoraInfo[];
  onChange: <K extends keyof GenerationForm>(field: K, value: GenerationForm[K]) => void;
  /** Hide the base model select (e.g. when a comparison varies the model). */
  hideModel?: boolean;
  /** Hide the strength slider (e.g. when a comparison varies the strength). */
  hideStrength?: boolean;
  /** Models the LoRA must work with; defaults to the selected base model. */
  loraTargets?: ModelInfo[];
  /** Models are still being fetched; don't claim none exist yet. */
  loading?: boolean;
}

export function usableModels(models: ModelInfo[]): ModelInfo[] {
  return models.filter((m) => m.available && m.architecture !== "unknown");
}

/** LoRAs usable with every given model; unknown-architecture LoRAs are allowed. */
export function compatibleLoras(loras: LoraInfo[], targets: ModelInfo[]): LoraInfo[] {
  if (targets.length === 0) return [];
  return loras.filter(
    (l) =>
      l.enabled &&
      l.available &&
      (l.base_architecture === "unknown" ||
        targets.every((model) => l.base_architecture === model.architecture)),
  );
}

export function ModelPanel({
  form,
  errors,
  models,
  loras,
  onChange,
  hideModel = false,
  hideStrength = false,
  loraTargets,
  loading = false,
}: ModelPanelProps) {
  const available = usableModels(models);
  const selectedModel = models.find((m) => String(m.id) === form.modelId);
  const targets = loraTargets ?? (selectedModel ? [selectedModel] : []);
  const loraOptions = compatibleLoras(loras, targets);
  const selectedLora = loras.find((l) => String(l.id) === form.loraId);

  return (
    <Panel title="Model">
      {!hideModel && (
        <>
          <label htmlFor="model" className="text-muted mb-1 block text-xs font-medium">
            Base model
          </label>
          <select
            id="model"
            value={form.modelId}
            aria-invalid={errors.modelId ? true : undefined}
            aria-describedby={errors.modelId ? "model-error" : undefined}
            onChange={(event) => {
              onChange("modelId", event.target.value);
              onChange("loraId", "");
            }}
            className={inputClass}
          >
            <option value="">{loading ? "Loading models…" : "Select a model"}</option>
            {available.map((model) => (
              <option key={model.id} value={model.id}>
                {model.name} ({architectureLabel(model.architecture)})
              </option>
            ))}
          </select>
          <FieldError id="model-error" message={errors.modelId} />
        </>
      )}
      {!loading && available.length === 0 && (
        <p className="text-muted mt-2 text-xs">
          No usable models found. Add one to the model directory, then rescan on the{" "}
          <Link href="/models" className="text-accent underline-offset-2 hover:underline">
            Models page
          </Link>
          .
        </p>
      )}

      <label
        htmlFor="lora"
        className={`text-muted mb-1 block text-xs font-medium ${hideModel ? "" : "mt-4"}`}
      >
        LoRA
      </label>
      <select
        id="lora"
        value={form.loraId}
        disabled={targets.length === 0}
        aria-invalid={errors.loraId ? true : undefined}
        aria-describedby={errors.loraId ? "lora-error" : undefined}
        onChange={(event) => {
          const lora = loras.find((l) => String(l.id) === event.target.value);
          onChange("loraId", event.target.value);
          if (lora) onChange("loraStrength", lora.default_strength);
        }}
        className={`${inputClass} disabled:opacity-50`}
      >
        <option value="">None</option>
        {loraOptions.map((lora) => (
          <option key={lora.id} value={lora.id}>
            {lora.name}
          </option>
        ))}
      </select>
      <FieldError id="lora-error" message={errors.loraId} />
      {selectedLora?.trigger_words && (
        <p className="text-muted mt-1 text-xs">
          Trigger words: <span className="text-ink font-mono">{selectedLora.trigger_words}</span>
        </p>
      )}

      {!hideStrength && (
        <div className="mt-4">
          <div className="mb-1 flex items-center justify-between">
            <label htmlFor="lora-strength" className="text-muted text-xs font-medium">
              LoRA strength
            </label>
            <span className="text-ink font-mono text-xs tabular-nums">
              {form.loraStrength.toFixed(2)}
            </span>
          </div>
          <input
            id="lora-strength"
            type="range"
            min={LIMITS.loraStrengthMin}
            max={LIMITS.loraStrengthMax}
            step={0.05}
            value={form.loraStrength}
            disabled={!form.loraId}
            onChange={(event) => onChange("loraStrength", Number(event.target.value))}
            className="w-full disabled:opacity-40"
          />
        </div>
      )}
    </Panel>
  );
}
