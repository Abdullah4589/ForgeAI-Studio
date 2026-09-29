"use client";

import Link from "next/link";
import { useState } from "react";
import { Play, RotateCcw, Trash2 } from "lucide-react";
import { Badge, Button } from "@/components/ui/primitives";
import { imageUrl } from "@/lib/api";
import { formatDate, formatDuration } from "@/lib/format";
import type { Generation } from "@/lib/types";

interface HistoryItemProps {
  generation: Generation;
  onDelete: (generation: Generation) => void;
}

export function HistoryItem({ generation, onDelete }: HistoryItemProps) {
  const [confirming, setConfirming] = useState(false);
  const cover = generation.images[0];

  return (
    <article
      aria-label={`Generation ${generation.id}`}
      className="border-line bg-panel grid grid-cols-[96px_1fr] gap-4 rounded-lg border p-3 sm:grid-cols-[128px_1fr]"
    >
      {cover ? (
        // eslint-disable-next-line @next/next/no-img-element -- next/image refuses local-IP sources
        <img
          src={imageUrl(cover.url)}
          alt={generation.prompt}
          loading="lazy"
          className="bg-raised aspect-square w-full rounded-md object-cover"
        />
      ) : (
        <div className="bg-raised aspect-square rounded-md" />
      )}
      <div className="min-w-0">
        <p className="line-clamp-2 text-sm leading-relaxed">{generation.prompt}</p>
        <div className="mt-2 flex flex-wrap gap-1.5">
          <Badge>{generation.model_name}</Badge>
          {generation.lora_name && (
            <Badge tone="accent">
              {generation.lora_name} @ {generation.lora_strength?.toFixed(2)}
            </Badge>
          )}
          <Badge>
            {generation.width}x{generation.height}
          </Badge>
          <Badge>{generation.steps} steps</Badge>
          <Badge>seed {generation.seed}</Badge>
          <Badge>
            {generation.images.length} image{generation.images.length === 1 ? "" : "s"}
          </Badge>
        </div>
        <p className="text-faint mt-2 text-xs">
          {formatDate(generation.created_at)} · {formatDuration(generation.duration_ms)} ·{" "}
          {generation.device}
        </p>
        <div className="mt-3 flex flex-wrap gap-2">
          <Link
            href={`/generate?from=${generation.id}`}
            className="border-line bg-raised hover:border-faint inline-flex items-center gap-2 rounded-md border px-3 py-1.5 text-sm"
          >
            <RotateCcw aria-hidden className="size-4" />
            Reuse settings
          </Link>
          <Link
            href={`/generate?from=${generation.id}&run=1`}
            className="border-line bg-raised hover:border-faint inline-flex items-center gap-2 rounded-md border px-3 py-1.5 text-sm"
          >
            <Play aria-hidden className="size-4" />
            Re-run
          </Link>
          {confirming ? (
            <>
              <Button variant="danger" onClick={() => onDelete(generation)}>
                Confirm delete
              </Button>
              <Button variant="ghost" onClick={() => setConfirming(false)}>
                Keep
              </Button>
            </>
          ) : (
            <Button variant="ghost" onClick={() => setConfirming(true)}>
              <Trash2 aria-hidden className="size-4" />
              Delete
            </Button>
          )}
        </div>
      </div>
    </article>
  );
}
