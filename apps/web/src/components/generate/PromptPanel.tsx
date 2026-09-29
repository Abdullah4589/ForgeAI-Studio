import { X } from "lucide-react";
import { FieldError, IconButton, inputClass, Panel } from "@/components/ui/primitives";
import { LIMITS, type FormErrors } from "@/lib/generation-form";

interface PromptPanelProps {
  prompt: string;
  negativePrompt: string;
  errors: FormErrors;
  onChange: (field: "prompt" | "negativePrompt", value: string) => void;
}

export function PromptPanel({ prompt, negativePrompt, errors, onChange }: PromptPanelProps) {
  return (
    <Panel title="Prompt">
      <PromptField
        id="prompt"
        label="Prompt"
        value={prompt}
        error={errors.prompt}
        rows={4}
        placeholder="A weathered lighthouse on a basalt cliff at dusk, volumetric fog"
        onChange={(value) => onChange("prompt", value)}
      />
      <div className="mt-3">
        <PromptField
          id="negative-prompt"
          label="Negative prompt"
          value={negativePrompt}
          error={errors.negativePrompt}
          rows={2}
          placeholder="blurry, low quality, watermark"
          onChange={(value) => onChange("negativePrompt", value)}
        />
      </div>
    </Panel>
  );
}

function PromptField({
  id,
  label,
  value,
  error,
  rows,
  placeholder,
  onChange,
}: {
  id: string;
  label: string;
  value: string;
  error?: string;
  rows: number;
  placeholder: string;
  onChange: (value: string) => void;
}) {
  const countId = `${id}-count`;
  const errorId = `${id}-error`;
  const over = value.length > LIMITS.promptMax;
  return (
    <div>
      <div className="mb-1 flex items-center justify-between">
        <label htmlFor={id} className="text-muted text-xs font-medium">
          {label}
        </label>
        <div className="flex items-center gap-1">
          <span
            id={countId}
            className={`font-mono text-xs tabular-nums ${over ? "text-danger" : "text-faint"}`}
          >
            {value.length}/{LIMITS.promptMax}
          </span>
          <IconButton
            label={`Clear ${label.toLowerCase()}`}
            onClick={() => onChange("")}
            disabled={!value}
            className="size-6 disabled:opacity-30"
          >
            <X aria-hidden className="size-3.5" />
          </IconButton>
        </div>
      </div>
      <textarea
        id={id}
        rows={rows}
        value={value}
        placeholder={placeholder}
        aria-invalid={error ? true : undefined}
        aria-describedby={error ? `${countId} ${errorId}` : countId}
        onChange={(event) => onChange(event.target.value)}
        className={`${inputClass} resize-y leading-relaxed`}
      />
      <FieldError id={errorId} message={error} />
    </div>
  );
}
