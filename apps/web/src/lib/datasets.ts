import type { DatasetImage, QualityFlag, UploadResult } from "./types";

// Keep in sync with MAX_FILES_PER_UPLOAD in apps/api/forge_api/services/dataset_service.py.
export const MAX_FILES_PER_REQUEST = 50;
export const ACCEPTED_IMAGE_TYPES = ".png,.jpg,.jpeg,.webp,image/png,image/jpeg,image/webp";

export const FLAG_LABELS: Record<QualityFlag, string> = {
  low_resolution: "Low resolution",
  extreme_aspect_ratio: "Extreme aspect ratio",
  possibly_blurry: "Possibly blurry",
  near_duplicate: "Near-duplicate",
};

export const FLAG_HINTS: Record<QualityFlag, string> = {
  low_resolution: "Shorter side is below the dataset's target resolution.",
  extreme_aspect_ratio: "Much wider than tall (or the reverse); training will crop heavily.",
  possibly_blurry: "Few sharp edges were detected. This is a heuristic; check the preview.",
  near_duplicate: "Looks almost identical to another image in this dataset.",
};

/** Move one item to a new index, returning a new array. */
export function moveItem<T>(items: T[], from: number, to: number): T[] {
  if (from === to || from < 0 || to < 0 || from >= items.length || to >= items.length) {
    return items;
  }
  const next = [...items];
  const [moved] = next.splice(from, 1);
  next.splice(to, 0, moved);
  return next;
}

/** Split files into request-sized batches the API accepts. */
export function batches<T>(items: T[], size = MAX_FILES_PER_REQUEST): T[][] {
  const result: T[][] = [];
  for (let i = 0; i < items.length; i += size) result.push(items.slice(i, i + size));
  return result;
}

export function mergeUploadResults(results: UploadResult[]): UploadResult {
  return {
    added: results.flatMap((r) => r.added),
    skipped: results.flatMap((r) => r.skipped),
  };
}

export function uploadSummary(result: UploadResult): string {
  const added = `Added ${result.added.length} image${result.added.length === 1 ? "" : "s"}`;
  return result.skipped.length ? `${added}, skipped ${result.skipped.length}.` : `${added}.`;
}

export type ImageFilter = "all" | "flagged" | "uncaptioned";

export function filterImages(images: DatasetImage[], filter: ImageFilter): DatasetImage[] {
  if (filter === "flagged") return images.filter((image) => image.flags.length > 0);
  if (filter === "uncaptioned") return images.filter((image) => !image.caption);
  return images;
}
