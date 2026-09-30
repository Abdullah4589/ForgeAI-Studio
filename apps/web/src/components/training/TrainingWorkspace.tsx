"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { ErrorBanner, PageHeader } from "@/components/ui/primitives";
import { useJob } from "@/hooks/useJob";
import { api, ApiError, errorMessage } from "@/lib/api";
import {
  EMPTY_TRAINING_FORM,
  toTrainingRequest,
  validateTrainingForm,
  type TrainingForm as Form,
  type TrainingFormErrors,
} from "@/lib/training";
import type { DatasetSummary, Job, ModelInfo, TrainingRun } from "@/lib/types";
import { ActiveRun } from "./ActiveRun";
import { RunList } from "./RunList";
import { TrainingForm, trainableModels } from "./TrainingForm";

const POLL_MS = 2000;

// Maps API validation fields onto form fields.
const API_FIELDS: Record<string, keyof Form> = {
  dataset_id: "datasetId",
  base_model_id: "baseModelId",
  name: "name",
  trigger_word: "triggerWord",
  resolution: "resolution",
  rank: "rank",
  alpha: "alpha",
  learning_rate: "learningRate",
  batch_size: "batchSize",
  steps: "steps",
  save_every: "saveEvery",
  seed: "seed",
  sample_count: "sampleCount",
  sample_steps: "sampleSteps",
};

export function TrainingWorkspace() {
  const [form, setForm] = useState<Form>(EMPTY_TRAINING_FORM);
  const [errors, setErrors] = useState<TrainingFormErrors>({});
  const [datasets, setDatasets] = useState<DatasetSummary[]>([]);
  const [models, setModels] = useState<ModelInfo[]>([]);
  const [runs, setRuns] = useState<TrainingRun[]>([]);
  const [activeRun, setActiveRun] = useState<TrainingRun | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const activeRunId = useRef<number | null>(null);

  const onFinished = useCallback(async (finished: Job) => {
    try {
      const id = activeRunId.current;
      const run = id === null ? null : await api.getTrainingRun(id);
      setActiveRun(run);
      setRuns(await api.listTrainingRuns());
      if (finished.status === "completed" && run) {
        setNotice(`Training finished. The LoRA "${run.name}" is ready on the Generate page.`);
      } else if (finished.status === "cancelled") {
        setNotice("Training cancelled.");
      } else if (finished.status === "failed") {
        setError(finished.error?.message ?? "Training failed.");
      }
    } catch (err) {
      setError(errorMessage(err));
    }
  }, []);
  const { job, running, elapsedMs, start, cancel } = useJob(onFinished);

  useEffect(() => {
    async function initialise() {
      try {
        const [datasetList, modelList, runList] = await Promise.all([
          api.listDatasets(),
          api.listModels(),
          api.listTrainingRuns(),
        ]);
        setDatasets(datasetList);
        setModels(modelList);
        setRuns(runList);
        setForm((current) => ({
          ...current,
          datasetId: current.datasetId || String(datasetList[0]?.id ?? ""),
          baseModelId: current.baseModelId || String(trainableModels(modelList)[0]?.id ?? ""),
        }));
        // Reattach to a run that is still going (e.g. after a page reload).
        const live = runList.find(
          (r) => (r.status === "running" || r.status === "queued") && r.job_id,
        );
        if (live?.job_id) {
          activeRunId.current = live.id;
          setActiveRun(live);
          const jobId = live.job_id;
          await start(() => api.getJob(jobId));
        }
      } catch (err) {
        setError(errorMessage(err));
      }
    }
    void initialise();
  }, [start]);

  // The job stream carries step and message; loss history and memory come from the run record.
  useEffect(() => {
    if (!running) return;
    const timer = setInterval(() => {
      const id = activeRunId.current;
      if (id === null) return;
      api.getTrainingRun(id).then(setActiveRun, () => {
        // Keep polling; the final state is fetched when the job ends.
      });
    }, POLL_MS);
    return () => clearInterval(timer);
  }, [running]);

  async function submit() {
    setError(null);
    setNotice(null);
    const validation = validateTrainingForm(form);
    setErrors(validation);
    if (Object.keys(validation).length > 0) return;
    try {
      await start(async () => {
        const created = await api.startTraining(toTrainingRequest(form));
        activeRunId.current = created.run_id;
        setActiveRun(await api.getTrainingRun(created.run_id));
        return created;
      });
      setRuns(await api.listTrainingRuns());
    } catch (err) {
      if (err instanceof ApiError && err.fields.length > 0) {
        const fieldErrors: TrainingFormErrors = {};
        for (const { field, message } of err.fields) {
          const key = API_FIELDS[field];
          if (key) fieldErrors[key] = message;
        }
        setErrors(fieldErrors);
      }
      setError(errorMessage(err));
    }
  }

  async function handleCancel() {
    const cancelError = await cancel();
    if (cancelError) setError(cancelError);
  }

  async function remove(run: TrainingRun) {
    try {
      await api.deleteTrainingRun(run.id);
      setRuns((current) => current.filter((r) => r.id !== run.id));
      if (activeRun?.id === run.id) setActiveRun(null);
    } catch (err) {
      setError(errorMessage(err));
    }
  }

  return (
    <div className="mx-auto max-w-[1100px] space-y-4">
      <PageHeader
        title="Training"
        description="Train a LoRA from a captioned dataset. Training runs in its own process; on CPU it takes a while."
      />
      <ErrorBanner message={error} />
      {notice && (
        <p role="status" aria-label="Training status" className="text-muted text-sm">
          {notice}
        </p>
      )}
      {activeRun && (running || activeRun.status === "running") && (
        <ActiveRun
          run={activeRun}
          job={job}
          running={running}
          elapsedMs={elapsedMs}
          onCancel={() => void handleCancel()}
        />
      )}
      <TrainingForm
        form={form}
        errors={errors}
        datasets={datasets}
        models={models}
        runs={runs}
        disabled={running}
        onChange={(changes) => {
          setForm((current) => ({ ...current, ...changes }));
          setErrors((current) => {
            const next = { ...current };
            for (const key of Object.keys(changes)) delete next[key as keyof Form];
            return next;
          });
        }}
        onSubmit={() => void submit()}
      />
      <section aria-label="Past runs" className="space-y-2">
        <h2 className="text-sm font-semibold">Runs</h2>
        <RunList runs={runs} onDelete={(run) => void remove(run)} />
      </section>
    </div>
  );
}
