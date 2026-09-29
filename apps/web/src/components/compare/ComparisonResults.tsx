"use client";

import Link from "next/link";
import { useState } from "react";
import { Download, Info, RotateCcw, Trash2 } from "lucide-react";
import { MetadataDialog } from "@/components/generate/MetadataDialog";
import { BlockedImage } from "@/components/ui/BlockedImage";
import { Badge, Button, IconButton } from "@/components/ui/primitives";
import { imageUrl } from "@/lib/api";
import { AXIS_LABELS, cellLabel } from "@/lib/compare-form";
import { formatDuration } from "@/lib/format";
import type { Comparison, ComparisonStatus, Generation, ModelInfo } from "@/lib/types";

const STATUS_TONE: Record<ComparisonStatus, "neutral" | "ok" | "warn" | "accent"> = {
  running: "accent",
  completed: "ok",
  cancelled: "neutral",
  failed: "warn",
  interrupted: "warn",
};

interface ComparisonResultsProps {
  comparison: Comparison;
  models: ModelInfo[];
  onDelete: (comparison: Comparison) => void;
}

export function ComparisonResults({ comparison, models, onDelete }: ComparisonResultsProps) {
  const [confirming, setConfirming] = useState(false);
  const [inspected, setInspected] = useState<Generation | null>(null);
  const byIndex = new Map(comparison.cells.map((cell) => [cell.comparison_index, cell]));

  return (
    <section aria-label="Comparison results" className="space-y-3">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="line-clamp-2 text-sm">{comparison.prompt}</p>
          <div className="mt-1.5 flex flex-wrap gap-1.5">
            <Badge>Varying {AXIS_LABELS[comparison.axis].toLowerCase()}</Badge>
            <Badge tone={STATUS_TONE[comparison.status]}>{comparison.status}</Badge>
          </div>
          {comparison.error_message && (
            <p className="text-danger mt-1 text-xs">{comparison.error_message}</p>
          )}
        </div>
        {confirming ? (
          <div className="flex gap-2">
            <Button variant="danger" onClick={() => onDelete(comparison)}>
              Confirm delete
            </Button>
            <Button variant="ghost" onClick={() => setConfirming(false)}>
              Keep
            </Button>
          </div>
        ) : (
          <Button variant="ghost" onClick={() => setConfirming(true)}>
            <Trash2 aria-hidden className="size-4" />
            Delete comparison
          </Button>
        )}
      </div>

      {/* Horizontal scroll keeps cells side by side on narrow screens instead of stacking. */}
      <ul
        aria-label="Comparison cells"
        className="grid gap-3 overflow-x-auto pb-2"
        style={{
          gridTemplateColumns: `repeat(${comparison.axis_values.length}, minmax(200px, 1fr))`,
        }}
      >
        {comparison.axis_values.map((value, index) => {
          const label = cellLabel(comparison.axis, value, models);
          const cell = byIndex.get(index);
          return (
            <li
              key={index}
              aria-label={label}
              className="border-line bg-panel overflow-hidden rounded-lg border"
            >
              <h3 className="border-line border-b px-3 py-2 text-sm font-semibold">{label}</h3>
              {cell ? (
                <CellBody cell={cell} label={label} onInspect={() => setInspected(cell)} />
              ) : (
                <div className="bg-raised text-faint flex aspect-square items-center justify-center p-4 text-center text-xs">
                  {comparison.status === "running" ? "Waiting…" : "Not generated"}
                </div>
              )}
            </li>
          );
        })}
      </ul>

      {inspected && inspected.images[0] && (
        <MetadataDialog
          generation={inspected}
          image={inspected.images[0]}
          onClose={() => setInspected(null)}
        />
      )}
    </section>
  );
}

function CellBody({
  cell,
  label,
  onInspect,
}: {
  cell: Generation;
  label: string;
  onInspect: () => void;
}) {
  const image = cell.images[0];
  return (
    <>
      {image?.safety_blocked ? (
        <BlockedImage />
      ) : image ? (
        // eslint-disable-next-line @next/next/no-img-element -- next/image refuses local-IP sources
        <img
          src={imageUrl(image.url)}
          alt={`${label}: ${cell.prompt}`}
          width={image.width}
          height={image.height}
          className="bg-raised h-auto w-full"
        />
      ) : (
        <div className="bg-raised aspect-square" />
      )}
      <dl className="text-muted grid grid-cols-[max-content_1fr] gap-x-2 px-3 pt-2 text-xs">
        <dt>Model</dt>
        <dd className="text-ink truncate">{cell.model_name}</dd>
        <dt>LoRA</dt>
        <dd className="text-ink truncate">
          {cell.lora_name ? `${cell.lora_name} @ ${cell.lora_strength?.toFixed(2)}` : "none"}
        </dd>
        <dt>Seed</dt>
        <dd className="text-ink font-mono">{cell.seed}</dd>
        <dt>Time</dt>
        <dd className="text-ink">{formatDuration(cell.duration_ms)}</dd>
      </dl>
      <div className="flex justify-end px-1.5 pb-1.5">
        {image && !image.safety_blocked && (
          <a
            href={imageUrl(image.url, true)}
            download
            aria-label={`Download ${label}`}
            title="Download"
            className="text-muted hover:bg-raised hover:text-ink inline-flex size-8 items-center justify-center rounded-md"
          >
            <Download aria-hidden className="size-4" />
          </a>
        )}
        <Link
          href={`/generate?from=${cell.id}`}
          aria-label={`Reuse settings of ${label}`}
          title="Reuse settings"
          className="text-muted hover:bg-raised hover:text-ink inline-flex size-8 items-center justify-center rounded-md"
        >
          <RotateCcw aria-hidden className="size-4" />
        </Link>
        <IconButton label={`View metadata of ${label}`} onClick={onInspect}>
          <Info aria-hidden className="size-4" />
        </IconButton>
      </div>
    </>
  );
}
