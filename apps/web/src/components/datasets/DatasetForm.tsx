"use client";

import { useState } from "react";
import { Button, inputClass } from "@/components/ui/primitives";
import type { DatasetInput } from "@/lib/types";

export const TARGET_RESOLUTIONS = [
  { value: 512, label: "512 px (SD 1.x)" },
  { value: 768, label: "768 px" },
  { value: 1024, label: "1024 px (SDXL)" },
];

interface DatasetFormProps {
  initial?: DatasetInput;
  submitLabel: string;
  idPrefix: string;
  onSubmit: (input: DatasetInput) => Promise<boolean>;
}

export function DatasetForm({ initial, submitLabel, idPrefix, onSubmit }: DatasetFormProps) {
  const [input, setInput] = useState<DatasetInput>(
    initial ?? { name: "", description: "", target_resolution: 512 },
  );
  const [nameError, setNameError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit() {
    if (!input.name.trim()) {
      setNameError("Enter a name.");
      return;
    }
    setBusy(true);
    const ok = await onSubmit({ ...input, name: input.name.trim() });
    setBusy(false);
    if (ok && !initial) setInput({ name: "", description: "", target_resolution: 512 });
  }

  return (
    <form
      noValidate
      onSubmit={(event) => {
        event.preventDefault();
        void submit();
      }}
      className="grid grid-cols-1 gap-3 sm:grid-cols-[1fr_200px]"
    >
      <div>
        <label htmlFor={`${idPrefix}-name`} className="text-muted mb-1 block text-xs font-medium">
          Name
        </label>
        <input
          id={`${idPrefix}-name`}
          value={input.name}
          maxLength={255}
          aria-invalid={nameError ? true : undefined}
          aria-describedby={nameError ? `${idPrefix}-name-error` : undefined}
          onChange={(event) => {
            setInput({ ...input, name: event.target.value });
            setNameError(null);
          }}
          className={inputClass}
        />
        {nameError && (
          <p id={`${idPrefix}-name-error`} className="text-danger mt-1 text-xs">
            {nameError}
          </p>
        )}
      </div>
      <div>
        <label
          htmlFor={`${idPrefix}-resolution`}
          className="text-muted mb-1 block text-xs font-medium"
        >
          Target resolution
        </label>
        <select
          id={`${idPrefix}-resolution`}
          value={input.target_resolution}
          onChange={(event) =>
            setInput({ ...input, target_resolution: Number(event.target.value) })
          }
          className={inputClass}
        >
          {TARGET_RESOLUTIONS.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
      </div>
      <div className="sm:col-span-2">
        <label
          htmlFor={`${idPrefix}-description`}
          className="text-muted mb-1 block text-xs font-medium"
        >
          Description
        </label>
        <textarea
          id={`${idPrefix}-description`}
          rows={2}
          maxLength={5000}
          value={input.description}
          onChange={(event) => setInput({ ...input, description: event.target.value })}
          className={inputClass}
        />
      </div>
      <div>
        <Button type="submit" variant="primary" disabled={busy}>
          {submitLabel}
        </Button>
      </div>
    </form>
  );
}
