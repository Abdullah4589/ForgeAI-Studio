"use client";

import { useState } from "react";
import { Sparkles, Square } from "lucide-react";
import { GenerationStatus } from "@/components/generate/GenerationStatus";
import { Button, Panel } from "@/components/ui/primitives";
import { OVERWRITE_OPTIONS, previewCaptioning } from "@/lib/captions";
import type { DatasetImage, Job, OverwriteMode } from "@/lib/types";

interface CaptionPanelProps {
  images: DatasetImage[];
  job: Job | null;
  running: boolean;
  elapsedMs: number;
  onStart: (mode: OverwriteMode) => void;
  onCancel: () => void;
}

export function CaptionPanel({
  images,
  job,
  running,
  elapsedMs,
  onStart,
  onCancel,
}: CaptionPanelProps) {
  const [mode, setMode] = useState<OverwriteMode>("empty_only");
  const [confirming, setConfirming] = useState(false);
  const preview = previewCaptioning(images, mode);

  function start() {
    // Replacing captions the user wrote is never done without an explicit second step.
    if (preview.manualOverwrites > 0 && !confirming) {
      setConfirming(true);
      return;
    }
    setConfirming(false);
    onStart(mode);
  }

  return (
    <Panel title="AI captions">
      <fieldset disabled={running}>
        <legend className="text-muted mb-2 text-xs font-medium">Caption</legend>
        <div className="grid gap-2 sm:grid-cols-3">
          {OVERWRITE_OPTIONS.map((option) => (
            <label
              key={option.value}
              className="border-line has-[:checked]:border-accent flex cursor-pointer gap-2 rounded-md border p-2 text-sm"
            >
              <input
                type="radio"
                name="caption-mode"
                value={option.value}
                checked={mode === option.value}
                onChange={() => {
                  setMode(option.value);
                  setConfirming(false);
                }}
                className="mt-0.5 accent-[var(--color-accent)]"
              />
              <span>
                <span className="block">{option.label}</span>
                <span className="text-faint block text-xs">{option.hint}</span>
              </span>
            </label>
          ))}
        </div>
      </fieldset>

      <div className="mt-3 flex flex-wrap items-center gap-3">
        {confirming ? (
          <>
            <p role="alert" className="text-danger text-sm">
              This will replace {preview.manualOverwrites} caption
              {preview.manualOverwrites === 1 ? "" : "s"} you wrote.
            </p>
            <Button variant="danger" onClick={start}>
              Replace my captions
            </Button>
            <Button variant="ghost" onClick={() => setConfirming(false)}>
              Keep them
            </Button>
          </>
        ) : (
          <Button variant="primary" onClick={start} disabled={running || preview.total === 0}>
            <Sparkles aria-hidden className="size-4" />
            Generate captions
          </Button>
        )}
        {running && (
          <Button variant="danger" onClick={onCancel}>
            <Square aria-hidden className="size-4" />
            Cancel
          </Button>
        )}
        <p className="text-muted text-xs" aria-live="polite">
          {preview.total === 0
            ? "Nothing to caption with this option."
            : `${preview.total} image${preview.total === 1 ? "" : "s"} will be captioned.`}
        </p>
      </div>
      <div className="mt-3">
        <GenerationStatus
          job={job}
          elapsedMs={elapsedMs}
          idleText="Ready. Choose which images to caption, then press Generate captions."
        />
      </div>
      <p className="text-faint mt-2 text-xs">
        Suggestions are a starting point: review and edit them. Cancelling keeps finished captions;
        the image being captioned finishes first.
      </p>
    </Panel>
  );
}
