import { Square } from "lucide-react";
import { GenerationStatus } from "@/components/generate/GenerationStatus";
import { Button, Panel } from "@/components/ui/primitives";
import { formatBytes } from "@/lib/format";
import { formatSeconds, remainingSeconds } from "@/lib/training";
import type { Job, TrainingRun } from "@/lib/types";
import { LossChart } from "./LossChart";

interface ActiveRunProps {
  run: TrainingRun;
  job: Job | null;
  running: boolean;
  elapsedMs: number;
  onCancel: () => void;
}

export function ActiveRun({ run, job, running, elapsedMs, onCancel }: ActiveRunProps) {
  const step = job?.step ?? run.current_step;
  const remaining = running ? remainingSeconds(step, run.steps, elapsedMs) : null;
  return (
    <Panel
      title={`Training "${run.name}"`}
      actions={
        running ? (
          <Button variant="danger" onClick={onCancel}>
            <Square aria-hidden className="size-4" />
            Cancel training
          </Button>
        ) : undefined
      }
    >
      <GenerationStatus
        job={job}
        elapsedMs={elapsedMs}
        idleText="Waiting for the run to start."
        runningLabel="Training"
      />
      <dl
        aria-label="Training progress"
        className="mt-3 grid grid-cols-2 gap-x-4 gap-y-1 text-sm sm:grid-cols-4"
      >
        <Stat label="Step" value={`${step} / ${run.steps}`} />
        <Stat label="Progress" value={`${Math.round((step / run.steps) * 100)}%`} />
        <Stat label="Loss" value={run.last_loss === null ? "-" : run.last_loss.toFixed(4)} />
        <Stat label="Time left" value={remaining === null ? "-" : `~${formatSeconds(remaining)}`} />
        <Stat label="Memory" value={formatBytes(run.peak_memory_bytes)} />
        <Stat label="Images" value={String(run.image_count)} />
        <Stat label="Resolution" value={`${run.resolution} px`} />
        <Stat label="Rank / alpha" value={`${run.rank} / ${run.alpha}`} />
      </dl>
      <div className="mt-3">
        <LossChart points={run.loss_history} />
      </div>
      <p className="text-faint mt-2 text-xs">
        Cancelling stops at the next step and keeps the last saved checkpoint.
      </p>
    </Panel>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-muted text-xs">{label}</dt>
      <dd className="font-mono tabular-nums">{value}</dd>
    </div>
  );
}
