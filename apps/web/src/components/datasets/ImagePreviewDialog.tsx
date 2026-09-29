"use client";

import { useEffect, useRef } from "react";
import { X } from "lucide-react";
import { IconButton } from "@/components/ui/primitives";
import { imageUrl } from "@/lib/api";
import { FLAG_LABELS } from "@/lib/datasets";
import { formatBytes } from "@/lib/format";
import type { DatasetImage } from "@/lib/types";

export function ImagePreviewDialog({
  image,
  onClose,
}: {
  image: DatasetImage;
  onClose: () => void;
}) {
  const ref = useRef<HTMLDialogElement>(null);

  useEffect(() => {
    const dialog = ref.current;
    // No close() in cleanup: see MetadataDialog (StrictMode would immediately re-close it).
    if (dialog && !dialog.open) dialog.showModal();
  }, []);

  return (
    <dialog
      ref={ref}
      onClose={onClose}
      aria-labelledby="preview-title"
      className="border-line bg-panel text-ink m-auto w-[min(960px,calc(100vw-2rem))] rounded-lg border p-0"
    >
      <div className="border-line flex items-center justify-between gap-3 border-b px-4 py-3">
        <h2 id="preview-title" className="truncate text-sm font-semibold">
          {image.original_filename}
        </h2>
        <IconButton label="Close preview" onClick={() => ref.current?.close()}>
          <X aria-hidden className="size-4" />
        </IconButton>
      </div>
      <div className="grid max-h-[80dvh] gap-4 overflow-y-auto p-4 md:grid-cols-[1fr_240px]">
        {/* eslint-disable-next-line @next/next/no-img-element -- next/image refuses local-IP sources */}
        <img
          src={imageUrl(image.url)}
          alt={image.caption || image.original_filename}
          className="bg-raised max-h-[70dvh] w-full object-contain"
        />
        <dl className="grid grid-cols-[max-content_1fr] content-start gap-x-3 gap-y-1.5 text-xs">
          <dt className="text-muted">Size</dt>
          <dd className="font-mono">
            {image.width}×{image.height}
          </dd>
          <dt className="text-muted">File</dt>
          <dd className="font-mono">
            {formatBytes(image.file_size_bytes)} {image.format}
          </dd>
          <dt className="text-muted">Sharpness</dt>
          <dd className="font-mono">{image.blur_score.toFixed(0)}</dd>
          <dt className="text-muted">Flags</dt>
          <dd>{image.flags.map((flag) => FLAG_LABELS[flag]).join(", ") || "None"}</dd>
          <dt className="text-muted">Caption</dt>
          <dd className="break-words">{image.caption || "(none)"}</dd>
        </dl>
      </div>
    </dialog>
  );
}
