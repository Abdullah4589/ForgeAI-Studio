"use client";

import { useState } from "react";
import { Copy, Download, Info, RotateCcw, Trash2 } from "lucide-react";
import { BlockedImage } from "@/components/ui/BlockedImage";
import { IconButton } from "@/components/ui/primitives";
import { imageUrl } from "@/lib/api";
import type { Generation, GenerationImage } from "@/lib/types";
import { MetadataDialog } from "./MetadataDialog";

interface ResultGridProps {
  generation: Generation;
  onReuse: (generation: Generation, image: GenerationImage) => void;
  onCopyPrompt: (prompt: string) => void;
  onDelete: (image: GenerationImage) => void;
}

export function ResultGrid({ generation, onReuse, onCopyPrompt, onDelete }: ResultGridProps) {
  const [inspected, setInspected] = useState<GenerationImage | null>(null);
  const columns = generation.images.length > 1 ? "sm:grid-cols-2" : "";

  return (
    <>
      <ul aria-label="Generated images" className={`grid grid-cols-1 gap-4 ${columns}`}>
        {generation.images.map((image) => (
          <li key={image.id} className="border-line bg-panel overflow-hidden rounded-lg border">
            {image.safety_blocked ? (
              <BlockedImage />
            ) : (
              // next/image refuses local-IP sources; these are already-optimised local PNGs.
              // eslint-disable-next-line @next/next/no-img-element
              <img
                src={imageUrl(image.url)}
                alt={`Generated image ${image.index + 1}: ${generation.prompt}`}
                width={image.width}
                height={image.height}
                className="bg-raised h-auto w-full"
              />
            )}
            <div className="flex items-center justify-between gap-2 px-2 py-1.5">
              <span className="text-muted font-mono text-xs tabular-nums">seed {image.seed}</span>
              <div className="flex">
                {!image.safety_blocked && (
                  <a
                    href={imageUrl(image.url, true)}
                    download
                    aria-label={`Download image ${image.index + 1}`}
                    title="Download"
                    className="text-muted hover:bg-raised hover:text-ink inline-flex size-8 items-center justify-center rounded-md"
                  >
                    <Download aria-hidden className="size-4" />
                  </a>
                )}
                <IconButton
                  label={`Reuse settings of image ${image.index + 1}`}
                  onClick={() => onReuse(generation, image)}
                >
                  <RotateCcw aria-hidden className="size-4" />
                </IconButton>
                <IconButton label="Copy prompt" onClick={() => onCopyPrompt(generation.prompt)}>
                  <Copy aria-hidden className="size-4" />
                </IconButton>
                <IconButton
                  label={`View metadata of image ${image.index + 1}`}
                  onClick={() => setInspected(image)}
                >
                  <Info aria-hidden className="size-4" />
                </IconButton>
                <IconButton
                  label={`Delete image ${image.index + 1}`}
                  onClick={() => onDelete(image)}
                  className="hover:text-danger"
                >
                  <Trash2 aria-hidden className="size-4" />
                </IconButton>
              </div>
            </div>
          </li>
        ))}
      </ul>
      {inspected && (
        <MetadataDialog
          generation={generation}
          image={inspected}
          onClose={() => setInspected(null)}
        />
      )}
    </>
  );
}
