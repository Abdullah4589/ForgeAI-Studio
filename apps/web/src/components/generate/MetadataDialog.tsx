"use client";

import { useEffect, useRef } from "react";
import { X } from "lucide-react";
import { IconButton } from "@/components/ui/primitives";
import { formatBytes, formatDate, formatDuration } from "@/lib/format";
import type { Generation, GenerationImage } from "@/lib/types";

interface MetadataDialogProps {
  generation: Generation;
  image: GenerationImage;
  onClose: () => void;
}

export function MetadataDialog({ generation, image, onClose }: MetadataDialogProps) {
  const ref = useRef<HTMLDialogElement>(null);

  useEffect(() => {
    const dialog = ref.current;
    // No close() in cleanup: its async "close" event would call onClose and unmount the dialog
    // during StrictMode's effect re-run. Unmounting removes it from the top layer anyway.
    if (dialog && !dialog.open) dialog.showModal();
  }, []);

  const rows: [string, string][] = [
    ["Prompt", generation.prompt],
    ["Negative prompt", generation.negative_prompt || "(none)"],
    ["Model", generation.model_name],
    [
      "LoRA",
      generation.lora_name
        ? `${generation.lora_name} @ ${generation.lora_strength?.toFixed(2)}`
        : "(none)",
    ],
    ["Seed", String(image.seed)],
    ["Size", `${image.width} x ${image.height}`],
    ["Steps", String(generation.steps)],
    ["Guidance scale", String(generation.guidance_scale)],
    ["Duration", formatDuration(generation.duration_ms)],
    ["Device", generation.device],
    ["File size", formatBytes(image.file_size_bytes)],
    ["Created", formatDate(generation.created_at)],
    ["Pipeline", JSON.stringify(generation.pipeline_config)],
  ];

  return (
    <dialog
      ref={ref}
      onClose={onClose}
      aria-labelledby="metadata-title"
      className="border-line bg-panel text-ink m-auto w-[min(640px,calc(100vw-2rem))] rounded-lg border p-0"
    >
      <div className="border-line flex items-center justify-between border-b px-4 py-3">
        <h2 id="metadata-title" className="text-sm font-semibold">
          Image metadata
        </h2>
        <IconButton label="Close" onClick={() => ref.current?.close()}>
          <X aria-hidden className="size-4" />
        </IconButton>
      </div>
      <dl className="grid max-h-[70dvh] grid-cols-[max-content_1fr] gap-x-4 gap-y-2 overflow-y-auto px-4 py-3 text-sm">
        {rows.map(([label, value]) => (
          <div key={label} className="contents">
            <dt className="text-muted">{label}</dt>
            <dd className="font-mono text-xs leading-5 break-words">{value}</dd>
          </div>
        ))}
      </dl>
    </dialog>
  );
}
