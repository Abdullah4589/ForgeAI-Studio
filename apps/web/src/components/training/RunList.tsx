"use client";

import Link from "next/link";
import { useState } from "react";
import { Trash2 } from "lucide-react";
import { BlockedImage } from "@/components/ui/BlockedImage";
import { Badge, Button, EmptyState, Panel } from "@/components/ui/primitives";
import { imageUrl } from "@/lib/api";
import { formatDate, formatDuration } from "@/lib/format";
import type { TrainingRun, TrainingStatus } from "@/lib/types";
import { LossChart } from "./LossChart";

const STATUS_TONE: Record<TrainingStatus, "neutral" | "ok" | "warn" | "accent"> = {
  queued: "accent",
  running: "accent",
  completed: "ok",
  failed: "warn",
  cancelled: "neutral",
  interrupted: "warn",
};

export function RunList({
  runs,
  onDelete,
}: {
  runs: TrainingRun[];
  onDelete: (run: TrainingRun) => void;
}) {
  if (runs.length === 0) {
    return (
      <EmptyState title="No training runs yet">
        Finished runs and their samples appear here.
      </EmptyState>
    );
  }
  return (
    <ul aria-label="Training runs" className="space-y-3">
      {runs.map((run) => (
        <RunCard key={run.id} run={run} onDelete={onDelete} />
      ))}
    </ul>
  );
}

function RunCard({ run, onDelete }: { run: TrainingRun; onDelete: (run: TrainingRun) => void }) {
  const [confirming, setConfirming] = useState(false);
  const duration =
    run.started_at && run.finished_at
      ? new Date(run.finished_at).getTime() - new Date(run.started_at).getTime()
      : null;
  const busy = run.status === "queued" || run.status === "running";
  return (
    <li aria-label={`Training run ${run.name}`}>
      <Panel>
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="min-w-0">
            <h3 className="font-medium">{run.name}</h3>
            <div className="mt-1.5 flex flex-wrap gap-1.5">
              <Badge tone={STATUS_TONE[run.status]}>{run.status}</Badge>
              <Badge>{run.dataset_name}</Badge>
              <Badge>{run.base_model_name}</Badge>
              <Badge>
                {run.resolution} px · {run.steps} steps · rank {run.rank}
              </Badge>
              {run.trigger_word && <Badge tone="accent">{run.trigger_word}</Badge>}
            </div>
            <p className="text-faint mt-1.5 text-xs">
              {formatDate(run.created_at)}
              {duration !== null && ` · ${formatDuration(duration)}`}
              {run.avg_step_seconds !== null && ` · ${run.avg_step_seconds.toFixed(2)} s/step`}
              {run.status !== "completed" && ` · stopped at step ${run.current_step}`}
            </p>
            {run.error_message && <p className="text-danger mt-1 text-sm">{run.error_message}</p>}
            {run.status === "cancelled" && run.has_checkpoint && (
              <p className="text-muted mt-1 text-xs">
                A checkpoint was kept in the training folder.
              </p>
            )}
          </div>
          <div className="flex flex-wrap items-center gap-2">
            {run.lora_id !== null && (
              <Link
                href="/loras"
                className="border-line bg-raised hover:border-faint rounded-md border px-3 py-1.5 text-sm"
              >
                View LoRA
              </Link>
            )}
            {confirming ? (
              <>
                <Button variant="danger" onClick={() => onDelete(run)}>
                  Delete run
                </Button>
                <Button variant="ghost" onClick={() => setConfirming(false)}>
                  Keep
                </Button>
              </>
            ) : (
              <Button
                variant="ghost"
                disabled={busy}
                onClick={() => setConfirming(true)}
                aria-label={`Delete run ${run.name}`}
              >
                <Trash2 aria-hidden className="size-4" />
              </Button>
            )}
          </div>
        </div>
        {run.loss_history.length > 1 && (
          <div className="mt-3 max-w-md">
            <LossChart points={run.loss_history} />
          </div>
        )}
        {run.samples.length > 0 && (
          <ul aria-label="Samples" className="mt-3 flex flex-wrap gap-2">
            {run.samples.map((sample, i) => (
              <li key={sample.index} className="w-32 overflow-hidden rounded-md">
                {sample.safety_blocked ? (
                  <BlockedImage compact />
                ) : (
                  // eslint-disable-next-line @next/next/no-img-element -- next/image refuses local-IP sources
                  <img
                    src={imageUrl(run.sample_urls[i])}
                    alt={`Sample ${sample.index + 1} from ${run.name}`}
                    className="bg-raised aspect-square w-full object-cover"
                  />
                )}
              </li>
            ))}
          </ul>
        )}
      </Panel>
    </li>
  );
}
