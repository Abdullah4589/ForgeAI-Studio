"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Sparkles, Square } from "lucide-react";
import { Button, EmptyState, ErrorBanner, PageHeader, Panel } from "@/components/ui/primitives";
import { useGenerationJob } from "@/hooks/useGenerationJob";
import { api, ApiError, errorMessage } from "@/lib/api";
import {
  EMPTY_FORM,
  formErrorsFromApi,
  formFromDefaults,
  formFromGeneration,
  toRequest,
  validateForm,
  type FormErrors,
  type GenerationForm,
} from "@/lib/generation-form";
import type { Generation, GenerationImage, Job, LoraInfo, ModelInfo } from "@/lib/types";
import { GenerationStatus } from "./GenerationStatus";
import { ModelPanel, usableModels } from "./ModelPanel";
import { PromptPanel } from "./PromptPanel";
import { ResultGrid } from "./ResultGrid";
import { SettingsPanel } from "./SettingsPanel";

interface GenerateWorkspaceProps {
  /** Prefill the form from this history entry (Reuse settings). */
  fromGenerationId: number | null;
  /** Submit immediately after prefilling (Re-run). */
  autoRun: boolean;
}

export function GenerateWorkspace({ fromGenerationId, autoRun }: GenerateWorkspaceProps) {
  const [form, setForm] = useState<GenerationForm>(EMPTY_FORM);
  const [errors, setErrors] = useState<FormErrors>({});
  const [models, setModels] = useState<ModelInfo[]>([]);
  const [loras, setLoras] = useState<LoraInfo[]>([]);
  const [ready, setReady] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [result, setResult] = useState<Generation | null>(null);
  const initialised = useRef(false);
  const edited = useRef(false);

  const onFinished = useCallback(async (job: Job) => {
    if (job.status === "failed") {
      setError(job.error?.message ?? "Generation failed.");
    } else if (job.status === "cancelled") {
      setNotice("Generation cancelled.");
    } else if (job.result?.generation_id) {
      try {
        setResult(await api.getGeneration(job.result.generation_id));
      } catch (err) {
        setError(errorMessage(err));
      }
    }
  }, []);

  const { job, elapsedMs, running, start, cancel } = useGenerationJob(onFinished);

  const submit = useCallback(
    async (values: GenerationForm) => {
      setNotice(null);
      setError(null);
      const validation = validateForm(values);
      setErrors(validation);
      if (Object.keys(validation).length > 0) return;
      try {
        await start(toRequest(values));
      } catch (err) {
        if (err instanceof ApiError && err.fields.length > 0) {
          setErrors(formErrorsFromApi(err.fields));
        }
        setError(errorMessage(err));
      }
    },
    [start],
  );

  useEffect(() => {
    // Guard against React StrictMode's double effect run, which would auto-run twice.
    if (initialised.current) return;
    initialised.current = true;

    async function initialise() {
      try {
        const [modelList, loraList, settings] = await Promise.all([
          api.listModels(),
          api.listLoras(),
          api.getSettings(),
        ]);
        setModels(modelList);
        setLoras(loraList);
        if (fromGenerationId !== null) {
          const previous = formFromGeneration(await api.getGeneration(fromGenerationId));
          setForm(previous);
          setNotice("Settings restored from history.");
          if (autoRun) void submit(previous);
          return;
        }
        const preferred = modelList.find((m) => m.loaded) ?? usableModels(modelList)[0];
        const preferredId = preferred ? String(preferred.id) : "";
        // If the user started typing before this slow initial fetch resolved, keep their input
        // and only fill in a model if none is chosen yet.
        setForm((current) =>
          edited.current
            ? { ...current, modelId: current.modelId || preferredId }
            : formFromDefaults(
                { ...EMPTY_FORM, modelId: preferredId },
                settings.generation_defaults,
              ),
        );
      } catch (err) {
        setError(errorMessage(err));
      } finally {
        setReady(true);
      }
    }
    void initialise();
  }, [fromGenerationId, autoRun, submit]);

  const update = useCallback(
    <K extends keyof GenerationForm>(field: K, value: GenerationForm[K]) => {
      edited.current = true;
      setForm((current) => ({ ...current, [field]: value }));
      setErrors((current) => ({ ...current, [field]: undefined }));
    },
    [],
  );

  function reuse(generation: Generation, image: GenerationImage) {
    // Reusing one image means reproducing exactly that image: its own seed, a single output.
    setForm({ ...formFromGeneration(generation, image.seed), numImages: "1" });
    setErrors({});
    setNotice(`Settings restored (seed ${image.seed}).`);
  }

  async function copyPrompt(prompt: string) {
    try {
      await navigator.clipboard.writeText(prompt);
      setNotice("Prompt copied to clipboard.");
    } catch {
      setError("Could not access the clipboard.");
    }
  }

  async function deleteImage(image: GenerationImage) {
    try {
      await api.deleteImage(image.id);
      setResult((current) => {
        if (!current) return null;
        const images = current.images.filter((i) => i.id !== image.id);
        return images.length ? { ...current, images } : null;
      });
    } catch (err) {
      setError(errorMessage(err));
    }
  }

  async function handleCancel() {
    const cancelError = await cancel();
    if (cancelError) setError(cancelError);
  }

  return (
    <div className="mx-auto max-w-[1400px]">
      <PageHeader title="Generate" description="Create images with your local diffusion models." />
      <form
        noValidate
        aria-busy={!ready}
        onSubmit={(event) => {
          event.preventDefault();
          void submit(form);
        }}
        className="grid grid-cols-1 gap-6 lg:grid-cols-[400px_1fr]"
      >
        <div className="space-y-4">
          <PromptPanel
            prompt={form.prompt}
            negativePrompt={form.negativePrompt}
            errors={errors}
            onChange={update}
          />
          <ModelPanel form={form} errors={errors} models={models} loras={loras} onChange={update} />
          <SettingsPanel form={form} errors={errors} onChange={update} />
        </div>

        <div className="min-w-0 space-y-4">
          <Panel>
            <div className="flex flex-wrap items-center gap-3">
              <Button type="submit" variant="primary" disabled={!ready || running}>
                <Sparkles aria-hidden className="size-4" />
                Generate
              </Button>
              {running && (
                <Button variant="danger" onClick={() => void handleCancel()}>
                  <Square aria-hidden className="size-4" />
                  Cancel
                </Button>
              )}
              {notice && (
                <p role="status" className="text-muted text-sm">
                  {notice}
                </p>
              )}
            </div>
            <div className="mt-4">
              <GenerationStatus job={job} elapsedMs={elapsedMs} />
            </div>
            <div className="mt-3">
              <ErrorBanner message={error} />
            </div>
          </Panel>

          {result ? (
            <ResultGrid
              generation={result}
              onReuse={reuse}
              onCopyPrompt={(prompt) => void copyPrompt(prompt)}
              onDelete={(image) => void deleteImage(image)}
            />
          ) : (
            <EmptyState title="No images yet">
              Generated images appear here and are saved to History automatically.
            </EmptyState>
          )}
        </div>
      </form>
    </div>
  );
}
