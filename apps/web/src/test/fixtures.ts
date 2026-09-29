// Shared test data builders (imported by tests only).
import type { DatasetImage } from "@/lib/types";

export function image(id: number, overrides: Partial<DatasetImage> = {}): DatasetImage {
  return {
    id,
    dataset_id: 1,
    position: id,
    original_filename: `${id}.png`,
    format: "PNG",
    width: 512,
    height: 512,
    file_size_bytes: 1000,
    blur_score: 900,
    caption: "",
    caption_source: null,
    caption_updated_at: null,
    created_at: "2026-01-01T00:00:00Z",
    flags: [],
    near_duplicate_of: [],
    url: `/api/datasets/1/images/${id}/file`,
    thumbnail_url: `/api/datasets/1/images/${id}/thumbnail`,
    ...overrides,
  };
}
