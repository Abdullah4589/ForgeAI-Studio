"use client";

import { useState } from "react";
import { ArrowDown, ArrowUp, GripVertical, Trash2 } from "lucide-react";
import { Badge, Button, IconButton, inputClass } from "@/components/ui/primitives";
import { imageUrl } from "@/lib/api";
import { FLAG_HINTS, FLAG_LABELS } from "@/lib/datasets";
import { formatBytes } from "@/lib/format";
import type { DatasetImage } from "@/lib/types";

interface DatasetImageCardProps {
  image: DatasetImage;
  index: number;
  total: number;
  /** Reordering is disabled while a filter hides some images. */
  canReorder: boolean;
  nameOf: (imageId: number) => string;
  onPreview: (image: DatasetImage) => void;
  onMove: (from: number, to: number) => void;
  onSaveCaption: (image: DatasetImage, caption: string) => Promise<boolean>;
  onRemove: (image: DatasetImage) => void;
  /** Ask the AI captioner for a suggestion for this one image. */
  onSuggest: (image: DatasetImage) => void;
  /** A job is running, so a new caption request can't start. */
  jobRunning: boolean;
  dragHandlers: {
    onDragStart: () => void;
    onDragOver: (event: React.DragEvent) => void;
    onDrop: () => void;
    onDragEnd: () => void;
  };
}

export function DatasetImageCard({
  image,
  index,
  total,
  canReorder,
  nameOf,
  onPreview,
  onMove,
  onSaveCaption,
  onRemove,
  onSuggest,
  jobRunning,
  dragHandlers,
}: DatasetImageCardProps) {
  const [draft, setDraft] = useState(image.caption);
  const [serverCaption, setServerCaption] = useState(image.caption);
  const [saving, setSaving] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [confirmingSuggest, setConfirmingSuggest] = useState(false);
  // When the caption changes on the server (e.g. an AI run finished), show it, unless the user
  // has unsaved edits in this box. Adjusting state during render avoids an extra effect pass.
  if (image.caption !== serverCaption) {
    setServerCaption(image.caption);
    if (draft.trim() === serverCaption) setDraft(image.caption);
  }
  const ownCaption = Boolean(image.caption) && image.caption_source !== "ai";
  const captionId = `caption-${image.id}`;
  const dirty = draft.trim() !== image.caption;
  const label = image.original_filename;

  async function save() {
    setSaving(true);
    if (await onSaveCaption(image, draft)) setDraft(draft.trim());
    setSaving(false);
  }

  return (
    <li
      aria-label={label}
      draggable={canReorder}
      onDragStart={dragHandlers.onDragStart}
      onDragOver={dragHandlers.onDragOver}
      onDrop={dragHandlers.onDrop}
      onDragEnd={dragHandlers.onDragEnd}
      className="border-line bg-panel flex flex-col overflow-hidden rounded-lg border"
    >
      <button
        type="button"
        onClick={() => onPreview(image)}
        aria-label={`Preview ${label}`}
        className="bg-raised relative block"
      >
        {/* eslint-disable-next-line @next/next/no-img-element -- next/image refuses local-IP sources */}
        <img
          src={imageUrl(image.thumbnail_url)}
          alt=""
          loading="lazy"
          className="aspect-square w-full object-contain"
        />
        <span className="bg-canvas/80 text-muted absolute top-1.5 left-1.5 rounded px-1.5 font-mono text-xs tabular-nums">
          #{index + 1}
        </span>
      </button>

      <div className="flex flex-1 flex-col gap-2 p-3">
        <div className="flex items-start justify-between gap-2">
          <p className="truncate text-sm font-medium" title={label}>
            {label}
          </p>
          {canReorder && <GripVertical aria-hidden className="text-faint size-4 shrink-0" />}
        </div>
        <p className="text-muted font-mono text-xs tabular-nums">
          {image.width}×{image.height} · {formatBytes(image.file_size_bytes)} · {image.format}
        </p>
        {image.flags.length > 0 && (
          <ul aria-label="Quality flags" className="flex flex-wrap gap-1">
            {image.flags.map((flag) => (
              <li key={flag} title={FLAG_HINTS[flag]}>
                <Badge tone="warn">{FLAG_LABELS[flag]}</Badge>
              </li>
            ))}
          </ul>
        )}
        {image.near_duplicate_of.length > 0 && (
          <p className="text-faint text-xs">
            Similar to {image.near_duplicate_of.map(nameOf).join(", ")}
          </p>
        )}

        <div className="flex items-center justify-between gap-2">
          <label htmlFor={captionId} className="text-muted text-xs font-medium">
            Caption
          </label>
          {image.caption && (
            <span title={image.caption_model ? `Written by ${image.caption_model}` : undefined}>
              <Badge tone={image.caption_source === "ai" ? "accent" : "neutral"}>
                {image.caption_source === "ai" ? "AI" : "Manual"}
              </Badge>
            </span>
          )}
        </div>
        <textarea
          id={captionId}
          rows={3}
          value={draft}
          placeholder="Describe the image for training…"
          onChange={(event) => setDraft(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter" && (event.ctrlKey || event.metaKey) && dirty) void save();
          }}
          className={`${inputClass} resize-y text-xs leading-relaxed`}
        />

        <div className="mt-auto flex flex-wrap items-center gap-1">
          <Button
            variant="primary"
            className="px-2 py-1 text-xs"
            disabled={!dirty || saving}
            onClick={() => void save()}
          >
            {saving ? "Saving…" : "Save caption"}
          </Button>
          {confirmingSuggest ? (
            <>
              <Button
                variant="danger"
                className="px-2 py-1 text-xs"
                onClick={() => {
                  setConfirmingSuggest(false);
                  onSuggest(image);
                }}
              >
                Replace my caption
              </Button>
              <Button
                variant="ghost"
                className="px-2 py-1 text-xs"
                onClick={() => setConfirmingSuggest(false)}
              >
                Keep
              </Button>
            </>
          ) : (
            <Button
              variant="ghost"
              className="px-2 py-1 text-xs"
              disabled={jobRunning}
              onClick={() => (ownCaption ? setConfirmingSuggest(true) : onSuggest(image))}
            >
              Suggest caption
            </Button>
          )}
          <div className="ml-auto flex">
            <IconButton
              label={`Move ${label} up`}
              disabled={!canReorder || index === 0}
              onClick={() => onMove(index, index - 1)}
              className="disabled:opacity-30"
            >
              <ArrowUp aria-hidden className="size-4" />
            </IconButton>
            <IconButton
              label={`Move ${label} down`}
              disabled={!canReorder || index === total - 1}
              onClick={() => onMove(index, index + 1)}
              className="disabled:opacity-30"
            >
              <ArrowDown aria-hidden className="size-4" />
            </IconButton>
            {confirming ? (
              <>
                <Button
                  variant="danger"
                  className="px-2 py-1 text-xs"
                  onClick={() => onRemove(image)}
                >
                  Remove
                </Button>
                <Button
                  variant="ghost"
                  className="px-2 py-1 text-xs"
                  onClick={() => setConfirming(false)}
                >
                  Keep
                </Button>
              </>
            ) : (
              <IconButton
                label={`Remove ${label}`}
                onClick={() => setConfirming(true)}
                className="hover:text-danger"
              >
                <Trash2 aria-hidden className="size-4" />
              </IconButton>
            )}
          </div>
        </div>
      </div>
    </li>
  );
}
