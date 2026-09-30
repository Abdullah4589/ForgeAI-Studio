import type { DatasetImage, Job, OverwriteMode } from "./types";

// Mirrors should_caption() in apps/api/forge_api/services/caption_service.py.
export function willCaption(image: DatasetImage, mode: OverwriteMode): boolean {
  if (!image.caption) return true;
  if (image.caption_source === "ai") return mode !== "empty_only";
  return mode === "everything";
}

export interface CaptionPreview {
  total: number;
  /** Manual captions this run would replace; these need explicit confirmation. */
  manualOverwrites: number;
}

export function previewCaptioning(images: DatasetImage[], mode: OverwriteMode): CaptionPreview {
  const targets = images.filter((image) => willCaption(image, mode));
  return {
    total: targets.length,
    manualOverwrites: targets.filter((image) => image.caption && image.caption_source !== "ai")
      .length,
  };
}

export const OVERWRITE_OPTIONS: { value: OverwriteMode; label: string; hint: string }[] = [
  {
    value: "empty_only",
    label: "Uncaptioned images",
    hint: "Only images without a caption.",
  },
  {
    value: "replace_ai",
    label: "Uncaptioned + AI captions",
    hint: "Also rewrite captions an earlier AI run produced. Your own captions are kept.",
  },
  {
    value: "everything",
    label: "Every image",
    hint: "Also replaces captions you wrote. You'll be asked to confirm.",
  },
];

export function captionSummary(job: Job): string {
  const captioned = job.result?.captioned ?? 0;
  const parts = [`Captioned ${captioned} image${captioned === 1 ? "" : "s"}`];
  if (job.result?.skipped) parts.push(`skipped ${job.result.skipped} changed meanwhile`);
  if (job.result?.failed) parts.push(`${job.result.failed} could not be read`);
  return `${parts.join(", ")}.`;
}
