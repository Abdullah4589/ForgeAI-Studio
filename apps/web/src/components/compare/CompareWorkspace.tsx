"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { Columns3, Square } from "lucide-react";
import { GenerationStatus } from "@/components/generate/GenerationStatus";
import { ModelPanel, usableModels } from "@/components/generate/ModelPanel";
import { PromptPanel } from "@/components/generate/PromptPanel";
import { SettingsPanel } from "@/components/generate/SettingsPanel";
import { Button, EmptyState, ErrorBanner, PageHeader, Panel } from "@/components/ui/primitives";
import { useJob } from "@/hooks/useJob";
import { api, ApiError, errorMessage } from "@/lib/api";
import {
  buildAxis,
  DEFAULT_AXIS_FORM,
  randomSeedList,
  toCompareRequest,
  validateSharedForm,
  type AxisForm,
} from "@/lib/compare-form";
import {
  EMPTY_FORM,
  formErrorsFromApi,
  formFromDefaults,
  type FormErrors,
  type GenerationForm,
} from "@/lib/generation-form";
import type { Comparison, ComparisonSummary, Job, LoraInfo, ModelInfo } from "@/lib/types";
import { AxisPanel } from "./AxisPanel";
import { ComparisonResults } from "./ComparisonResults";
import { RecentComparisons } from "./RecentComparisons";

export function CompareWorkspace({ comparisonId }: { comparisonId: number | null }) {
  const router = useRouter();
  const [form, setForm] = useState<GenerationForm>(EMPTY_FORM);
  const [axis, setAxis] = useState<AxisForm>(DEFAULT_AXIS_FORM);
  const [errors, setErrors] = useState<FormErrors>({});
  const [axisError, setAxisError] = useState<string | undefined>();
  const [models, setModels] = useState<ModelInfo[]>([]);
  const [loras, setLoras] = useState<LoraInfo[]>([]);
  const [recent, setRecent] = useState<ComparisonSummary[]>([]);
  const [comparison, setComparison] = useState<Comparison | null>(null);
  const [ready, setReady] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const edited = useRef(false);
  const activeComparisonId = useRef<number | null>(null);

  const refreshRecent = useCallback(async () => {
    setRecent(await api.listComparisons());
  }, []);

  const showComparison = useCallback(async (id: number) => {
    setComparison(await api.getComparison(id));
  }, []);

  const onFinished = useCallback(
    async (job: Job) => {
      if (job.status === "failed") setError(job.error?.message ?? "Comparison failed.");
      if (job.status === "cancelled") setNotice("Comparison cancelled. Finished cells were kept.");
      const id = job.result?.comparison_id ?? activeComparisonId.current;
      try {
        if (id !== null) await showComparison(id);
        await refreshRecent();
      } catch (err) {
        setError(errorMessage(err));
      }
    },
    [showComparison, refreshRecent],
  );

  const { job, elapsedMs, running, start, cancel } = useJob(onFinished);

  useEffect(() => {
    async function initialise() {
      try {
        const [modelList, loraList, settings] = await Promise.all([
          api.listModels(),
          api.listLoras(),
          api.getSettings(),
          refreshRecent(),
        ]);
        setModels(modelList);
        setLoras(loraList);
        const preferred = modelList.find((m) => m.loaded) ?? usableModels(modelList)[0];
        const preferredId = preferred ? String(preferred.id) : "";
        // Keep anything the user typed while this was loading (see GenerateWorkspace).
        setForm((current) =>
          edited.current
            ? { ...current, modelId: current.modelId || preferredId }
            : formFromDefaults(
                { ...EMPTY_FORM, modelId: preferredId },
                settings.generation_defaults,
              ),
        );
        const hasLora = loraList.some((l) => l.enabled && l.available);
        setAxis((current) =>
          edited.current || hasLora
            ? current
            : { ...current, kind: "seed", seeds: current.seeds || randomSeedList() },
        );
      } catch (err) {
        setError(errorMessage(err));
      } finally {
        setReady(true);
      }
    }
    void initialise();
  }, [refreshRecent]);

  useEffect(() => {
    if (comparisonId === null) return;
    let stale = false;
    api.getComparison(comparisonId).then(
      (loaded) => {
        if (!stale) setComparison(loaded);
      },
      (err: unknown) => {
        if (!stale) setError(errorMessage(err));
      },
    );
    return () => {
      stale = true;
    };
  }, [comparisonId]);

  const update = useCallback(
    <K extends keyof GenerationForm>(field: K, value: GenerationForm[K]) => {
      edited.current = true;
      setForm((current) => ({ ...current, [field]: value }));
      setErrors((current) => ({ ...current, [field]: undefined }));
    },
    [],
  );

  function updateAxis(next: AxisForm) {
    edited.current = true;
    setAxis(next);
    setAxisError(undefined);
  }

  async function submit() {
    setNotice(null);
    setError(null);
    const formErrors = validateSharedForm(form, axis.kind);
    const built = buildAxis(axis);
    setErrors(formErrors);
    setAxisError(built.error);
    if (Object.keys(formErrors).length > 0 || !built.axis) return;
    try {
      await start(async () => {
        const created = await api.compare(toCompareRequest(form, built.axis!));
        activeComparisonId.current = created.comparison_id;
        router.replace(`/compare?id=${created.comparison_id}`, { scroll: false });
        return created;
      });
    } catch (err) {
      if (err instanceof ApiError && err.fields.length > 0) {
        setErrors(formErrorsFromApi(err.fields));
      }
      setError(errorMessage(err));
    }
  }

  async function remove(target: Comparison) {
    try {
      await api.deleteComparison(target.id);
      setComparison(null);
      setNotice("Comparison deleted.");
      router.replace("/compare", { scroll: false });
      await refreshRecent();
    } catch (err) {
      setError(errorMessage(err));
    }
  }

  async function handleCancel() {
    const cancelError = await cancel();
    if (cancelError) setError(cancelError);
  }

  const selectedModelIds = new Set(axis.modelIds);
  const loraTargets =
    axis.kind === "model" ? models.filter((m) => selectedModelIds.has(String(m.id))) : undefined;

  return (
    <div className="mx-auto max-w-[1400px]">
      <PageHeader
        title="Compare"
        description="Generate one prompt several times, changing a single setting, and see the results side by side."
      />
      <form
        noValidate
        aria-busy={!ready}
        onSubmit={(event) => {
          event.preventDefault();
          void submit();
        }}
        className="grid grid-cols-1 gap-6 lg:grid-cols-[400px_1fr]"
      >
        <div className="space-y-4">
          <AxisPanel axis={axis} models={models} error={axisError} onChange={updateAxis} />
          <PromptPanel
            prompt={form.prompt}
            negativePrompt={form.negativePrompt}
            errors={errors}
            onChange={update}
          />
          <ModelPanel
            form={form}
            errors={errors}
            models={models}
            loras={loras}
            onChange={update}
            hideModel={axis.kind === "model"}
            hideStrength={axis.kind === "lora_strength"}
            loraTargets={loraTargets}
          />
          <SettingsPanel
            form={form}
            errors={errors}
            onChange={update}
            hidden={axis.kind === "seed" ? ["seed", "numImages"] : ["numImages"]}
          />
        </div>

        <div className="min-w-0 space-y-4">
          <Panel>
            <div className="flex flex-wrap items-center gap-3">
              <Button type="submit" variant="primary" disabled={!ready || running}>
                <Columns3 aria-hidden className="size-4" />
                Compare
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

          {comparison ? (
            <ComparisonResults comparison={comparison} models={models} onDelete={remove} />
          ) : (
            <EmptyState title="No comparison selected">
              Choose what to vary, then press Compare. Every cell is also saved to History.
            </EmptyState>
          )}
          <RecentComparisons
            comparisons={recent}
            models={models}
            activeId={comparison?.id ?? null}
          />
        </div>
      </form>
    </div>
  );
}
