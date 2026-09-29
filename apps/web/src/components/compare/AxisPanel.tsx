import { Dices } from "lucide-react";
import { Button, FieldError, inputClass, Panel } from "@/components/ui/primitives";
import { usableModels } from "@/components/generate/ModelPanel";
import {
  AXIS_LABELS,
  MAX_CELLS,
  MIN_CELLS,
  randomSeedList,
  type AxisForm,
} from "@/lib/compare-form";
import { architectureLabel } from "@/lib/format";
import type { CompareAxisKind, ModelInfo } from "@/lib/types";

interface AxisPanelProps {
  axis: AxisForm;
  models: ModelInfo[];
  error?: string;
  onChange: (axis: AxisForm) => void;
}

export function AxisPanel({ axis, models, error, onChange }: AxisPanelProps) {
  const errorProps = error ? { "aria-invalid": true, "aria-describedby": "axis-error" } : {};

  return (
    <Panel title="Compare">
      <label htmlFor="axis-kind" className="text-muted mb-1 block text-xs font-medium">
        Vary
      </label>
      <select
        id="axis-kind"
        value={axis.kind}
        onChange={(event) => onChange({ ...axis, kind: event.target.value as CompareAxisKind })}
        className={inputClass}
      >
        {(Object.keys(AXIS_LABELS) as CompareAxisKind[]).map((kind) => (
          <option key={kind} value={kind}>
            {AXIS_LABELS[kind]}
          </option>
        ))}
      </select>

      <div className="mt-4">
        {axis.kind === "lora_strength" && (
          <>
            <label htmlFor="axis-strengths" className="text-muted mb-1 block text-xs font-medium">
              Strengths
            </label>
            <input
              id="axis-strengths"
              value={axis.strengths}
              placeholder="none, 0.4, 0.8"
              onChange={(event) => onChange({ ...axis, strengths: event.target.value })}
              className={`${inputClass} font-mono`}
              {...errorProps}
            />
            <p className="text-faint mt-1 text-xs">
              Comma-separated, {MIN_CELLS} to {MAX_CELLS} values. Use &quot;none&quot; for a
              baseline without the LoRA.
            </p>
          </>
        )}

        {axis.kind === "seed" && (
          <>
            <label htmlFor="axis-seeds" className="text-muted mb-1 block text-xs font-medium">
              Seeds
            </label>
            <div className="flex gap-2">
              <input
                id="axis-seeds"
                value={axis.seeds}
                placeholder="1, 2, 3"
                onChange={(event) => onChange({ ...axis, seeds: event.target.value })}
                className={`${inputClass} font-mono`}
                {...errorProps}
              />
              <Button onClick={() => onChange({ ...axis, seeds: randomSeedList() })}>
                <Dices aria-hidden className="size-4" />
                Random seeds
              </Button>
            </div>
            <p className="text-faint mt-1 text-xs">
              Comma-separated, {MIN_CELLS} to {MAX_CELLS} seeds.
            </p>
          </>
        )}

        {axis.kind === "model" && (
          <fieldset {...errorProps}>
            <legend className="text-muted mb-1 text-xs font-medium">
              Models ({MIN_CELLS} to {MAX_CELLS})
            </legend>
            <div className="space-y-1.5">
              {usableModels(models).map((model) => {
                const id = String(model.id);
                const checked = axis.modelIds.includes(id);
                return (
                  <label key={model.id} className="flex items-center gap-2 text-sm">
                    <input
                      type="checkbox"
                      checked={checked}
                      onChange={() =>
                        onChange({
                          ...axis,
                          modelIds: checked
                            ? axis.modelIds.filter((m) => m !== id)
                            : [...axis.modelIds, id],
                        })
                      }
                      className="size-4 accent-[var(--color-accent)]"
                    />
                    {model.name}
                    <span className="text-faint text-xs">
                      {architectureLabel(model.architecture)}
                    </span>
                  </label>
                );
              })}
            </div>
            <p className="text-faint mt-2 text-xs">
              Models are loaded one after another, which is slow on CPU.
            </p>
          </fieldset>
        )}
        <FieldError id="axis-error" message={error} />
      </div>
    </Panel>
  );
}
