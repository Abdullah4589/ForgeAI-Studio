"use client";

import { useEffect, useState } from "react";
import { Button, ErrorBanner, inputClass, PageHeader, Panel } from "@/components/ui/primitives";
import { api, ApiError, errorMessage } from "@/lib/api";
import type { AppSettings, GenerationDefaults } from "@/lib/types";

const NUMERIC_FIELDS: {
  key: Exclude<keyof GenerationDefaults, "negative_prompt">;
  label: string;
  step?: number;
}[] = [
  { key: "width", label: "Default width", step: 8 },
  { key: "height", label: "Default height", step: 8 },
  { key: "steps", label: "Default steps" },
  { key: "guidance_scale", label: "Default guidance scale", step: 0.5 },
  { key: "num_images", label: "Default number of images" },
];

export default function SettingsPage() {
  const [settings, setSettings] = useState<AppSettings | null>(null);
  const [defaults, setDefaults] = useState<GenerationDefaults | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    api.getSettings().then(
      (result) => {
        setSettings(result);
        setDefaults(result.generation_defaults);
      },
      (err: unknown) => setError(errorMessage(err)),
    );
  }, []);

  async function save() {
    if (!defaults) return;
    setError(null);
    setSaved(false);
    try {
      setDefaults(await api.saveGenerationDefaults(defaults));
      setSaved(true);
    } catch (err) {
      const detail =
        err instanceof ApiError && err.fields.length
          ? err.fields.map((f) => `${f.field}: ${f.message}`).join("; ")
          : null;
      setError(detail ?? errorMessage(err));
    }
  }

  const runtime = settings?.runtime;

  return (
    <div className="mx-auto max-w-[900px] space-y-4">
      <PageHeader title="Settings" />
      <ErrorBanner message={error} />
      {runtime && (
        <Panel title="Runtime configuration">
          <p className="text-muted mb-3 text-sm">
            Set through environment variables (see .env.example). Restart the API to change them.
          </p>
          <dl className="grid grid-cols-[max-content_1fr] gap-x-4 gap-y-1.5 text-sm">
            {(
              [
                ["Model directory", runtime.model_directory],
                ["LoRA directory", runtime.lora_directory],
                ["Output directory", runtime.output_directory],
                ["Dataset directory", runtime.dataset_directory],
                ["Device", runtime.device],
                ["Generation backend", runtime.generation_backend],
                ["CPU offload", runtime.enable_cpu_offload ? "On" : "Off"],
                [
                  "Idle model unload",
                  runtime.model_idle_unload_seconds
                    ? `${runtime.model_idle_unload_seconds} s`
                    : "Never",
                ],
                ["Max upload size", `${runtime.max_upload_size_mb} MB`],
              ] as const
            ).map(([label, value]) => (
              <div key={label} className="contents">
                <dt className="text-muted">{label}</dt>
                <dd className="font-mono text-xs leading-5 break-all">{value}</dd>
              </div>
            ))}
          </dl>
        </Panel>
      )}
      {defaults && (
        <Panel title="Generation defaults">
          <form
            onSubmit={(event) => {
              event.preventDefault();
              void save();
            }}
          >
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              {NUMERIC_FIELDS.map(({ key, label, step }) => (
                <div key={key}>
                  <label
                    htmlFor={`default-${key}`}
                    className="text-muted mb-1 block text-xs font-medium"
                  >
                    {label}
                  </label>
                  <input
                    id={`default-${key}`}
                    type="number"
                    step={step}
                    value={defaults[key]}
                    onChange={(event) =>
                      setDefaults({ ...defaults, [key]: Number(event.target.value) })
                    }
                    className={`${inputClass} font-mono`}
                  />
                </div>
              ))}
              <div className="sm:col-span-2">
                <label
                  htmlFor="default-negative"
                  className="text-muted mb-1 block text-xs font-medium"
                >
                  Default negative prompt
                </label>
                <textarea
                  id="default-negative"
                  rows={2}
                  value={defaults.negative_prompt}
                  onChange={(event) =>
                    setDefaults({ ...defaults, negative_prompt: event.target.value })
                  }
                  className={inputClass}
                />
              </div>
            </div>
            <div className="mt-4 flex items-center gap-3">
              <Button type="submit" variant="primary">
                Save defaults
              </Button>
              {saved && (
                <p role="status" className="text-ok text-sm">
                  Defaults saved.
                </p>
              )}
            </div>
          </form>
        </Panel>
      )}
    </div>
  );
}
