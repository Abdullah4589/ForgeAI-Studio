import { Dices } from "lucide-react";
import { FieldError, IconButton, inputClass, Panel } from "@/components/ui/primitives";
import { LIMITS, randomSeed, type FormErrors, type GenerationForm } from "@/lib/generation-form";

type NumericField = "width" | "height" | "steps" | "guidanceScale" | "seed" | "numImages";

interface SettingsPanelProps {
  form: GenerationForm;
  errors: FormErrors;
  onChange: (field: NumericField, value: string) => void;
}

export function SettingsPanel({ form, errors, onChange }: SettingsPanelProps) {
  const field = (key: NumericField, label: string, props: NumberInputProps = {}) => (
    <NumberField
      id={key}
      label={label}
      value={form[key]}
      error={errors[key]}
      onChange={(value) => onChange(key, value)}
      {...props}
    />
  );

  return (
    <Panel title="Settings">
      <div className="grid grid-cols-2 gap-3">
        {field("width", "Width", { min: LIMITS.sizeMin, max: LIMITS.sizeMax, step: 8 })}
        {field("height", "Height", { min: LIMITS.sizeMin, max: LIMITS.sizeMax, step: 8 })}
        {field("steps", "Steps", { min: LIMITS.stepsMin, max: LIMITS.stepsMax })}
        {field("guidanceScale", "Guidance scale", {
          min: LIMITS.guidanceMin,
          max: LIMITS.guidanceMax,
          step: 0.5,
        })}
        <div>
          <label htmlFor="seed" className="text-muted mb-1 block text-xs font-medium">
            Seed
          </label>
          <div className="flex gap-1">
            <input
              id="seed"
              inputMode="numeric"
              value={form.seed}
              placeholder="Random"
              aria-invalid={errors.seed ? true : undefined}
              aria-describedby={errors.seed ? "seed-error" : undefined}
              onChange={(event) => onChange("seed", event.target.value)}
              className={`${inputClass} font-mono`}
            />
            <IconButton
              label="Random seed"
              onClick={() => onChange("seed", randomSeed())}
              className="border-line size-9 shrink-0 border"
            >
              <Dices aria-hidden className="size-4" />
            </IconButton>
          </div>
          <FieldError id="seed-error" message={errors.seed} />
        </div>
        {field("numImages", "Images", { min: LIMITS.imagesMin, max: LIMITS.imagesMax })}
      </div>
    </Panel>
  );
}

interface NumberInputProps {
  min?: number;
  max?: number;
  step?: number;
}

function NumberField({
  id,
  label,
  value,
  error,
  onChange,
  ...props
}: NumberInputProps & {
  id: string;
  label: string;
  value: string;
  error?: string;
  onChange: (value: string) => void;
}) {
  const errorId = `${id}-error`;
  return (
    <div>
      <label htmlFor={id} className="text-muted mb-1 block text-xs font-medium">
        {label}
      </label>
      <input
        id={id}
        type="number"
        value={value}
        aria-invalid={error ? true : undefined}
        aria-describedby={error ? errorId : undefined}
        onChange={(event) => onChange(event.target.value)}
        className={`${inputClass} font-mono tabular-nums`}
        {...props}
      />
      <FieldError id={errorId} message={error} />
    </div>
  );
}
