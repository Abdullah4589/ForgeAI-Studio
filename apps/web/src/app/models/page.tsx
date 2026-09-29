"use client";

import { useEffect, useState } from "react";
import { RefreshCw } from "lucide-react";
import {
  Badge,
  Button,
  EmptyState,
  ErrorBanner,
  PageHeader,
  Panel,
} from "@/components/ui/primitives";
import { api, errorMessage } from "@/lib/api";
import { architectureLabel, formatBytes, formatDate } from "@/lib/format";
import type { ModelInfo } from "@/lib/types";

export default function ModelsPage() {
  const [models, setModels] = useState<ModelInfo[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<number | "rescan" | null>(null);

  useEffect(() => {
    api.listModels().then(setModels, (err: unknown) => setError(errorMessage(err)));
  }, []);

  async function run(id: number | "rescan", action: () => Promise<unknown>) {
    setBusyId(id);
    setError(null);
    try {
      await action();
      setModels(await api.listModels());
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusyId(null);
    }
  }

  return (
    <div className="mx-auto max-w-[1100px]">
      <PageHeader
        title="Models"
        description="Base models found in the model directory. Only one model is kept in memory at a time."
        actions={
          <Button onClick={() => void run("rescan", api.rescanModels)} disabled={busyId !== null}>
            <RefreshCw
              aria-hidden
              className={`size-4 ${busyId === "rescan" ? "animate-spin" : ""}`}
            />
            Rescan
          </Button>
        }
      />
      <div className="space-y-3">
        <ErrorBanner message={error} />
        {models?.length === 0 && (
          <EmptyState title="No models installed">
            Put a Diffusers model folder or a .safetensors checkpoint in the model directory, then
            press Rescan.
          </EmptyState>
        )}
        {models?.map((model) => (
          <Panel key={model.id}>
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div className="min-w-0">
                <h2 className="font-medium">{model.name}</h2>
                <p className="text-faint mt-0.5 truncate font-mono text-xs">{model.path}</p>
                <div className="mt-2 flex flex-wrap gap-1.5">
                  <Badge tone={model.architecture === "unknown" ? "warn" : "neutral"}>
                    {architectureLabel(model.architecture)}
                  </Badge>
                  <Badge>
                    {model.source_type === "diffusers" ? "Diffusers folder" : "Single file"}
                  </Badge>
                  <Badge>{formatBytes(model.file_size_bytes)}</Badge>
                  {model.loaded && <Badge tone="ok">Loaded</Badge>}
                  {!model.available && <Badge tone="warn">Files missing</Badge>}
                </div>
                <dl className="text-muted mt-2 grid grid-cols-[max-content_1fr] gap-x-3 text-xs">
                  <dt>Added</dt>
                  <dd>{formatDate(model.created_at)}</dd>
                  <dt>Resolutions</dt>
                  <dd className="font-mono">
                    {model.supported_resolutions.length
                      ? model.supported_resolutions.map(([w, h]) => `${w}x${h}`).join(", ")
                      : "n/a"}
                  </dd>
                </dl>
              </div>
              {model.loaded ? (
                <Button
                  onClick={() => void run(model.id, api.unloadModel)}
                  disabled={busyId !== null}
                >
                  {busyId === model.id ? "Unloading…" : "Unload"}
                </Button>
              ) : (
                <Button
                  onClick={() => void run(model.id, () => api.loadModel(model.id))}
                  disabled={busyId !== null || !model.available || model.architecture === "unknown"}
                >
                  {busyId === model.id ? "Loading…" : "Load"}
                </Button>
              )}
            </div>
          </Panel>
        ))}
      </div>
    </div>
  );
}
