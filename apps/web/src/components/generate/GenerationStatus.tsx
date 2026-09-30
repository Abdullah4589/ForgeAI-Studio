import { formatDuration } from "@/lib/format";
import type { Job } from "@/lib/types";

const STATUS_LABELS: Record<Job["status"], string> = {
  queued: "Queued",
  running: "Generating",
  completed: "Completed",
  failed: "Failed",
  cancelled: "Cancelled",
};

export function GenerationStatus({
  job,
  elapsedMs,
  idleText = "Ready. Configure your prompt and press Generate.",
  runningLabel = "Generating",
}: {
  job: Job | null;
  elapsedMs: number;
  /** Hint shown before any job has started. */
  idleText?: string;
  /** What a running job is called, e.g. "Training". */
  runningLabel?: string;
}) {
  if (!job) {
    return <p className="text-faint text-sm">{idleText}</p>;
  }
  const percent = job.total_steps > 0 ? Math.round((job.step / job.total_steps) * 100) : 0;
  const duration =
    job.finished_at && job.started_at
      ? Math.round((job.finished_at - job.started_at) * 1000)
      : elapsedMs;
  const barColor =
    job.status === "failed" ? "bg-danger" : job.status === "cancelled" ? "bg-faint" : "bg-accent";

  return (
    <div className="space-y-2" aria-live="polite">
      <div className="flex items-center justify-between text-sm">
        <span>
          <span className="font-medium">
            {job.status === "running" ? runningLabel : STATUS_LABELS[job.status]}
          </span>
          {job.status === "running" && <span className="text-muted"> - {job.message}</span>}
        </span>
        <span className="text-muted font-mono text-xs tabular-nums" aria-label="Duration">
          {formatDuration(duration)}
        </span>
      </div>
      <div
        role="progressbar"
        aria-label="Generation progress"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={percent}
        className="bg-raised h-1.5 overflow-hidden rounded-full"
      >
        <div
          className={`h-full origin-left rounded-full transition-transform duration-200 ${barColor}`}
          style={{ transform: `scaleX(${percent / 100})` }}
        />
      </div>
    </div>
  );
}
