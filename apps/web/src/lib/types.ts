// Mirrors the FastAPI response schemas in apps/api/forge_api/schemas.

export interface ModelInfo {
  id: number;
  name: string;
  path: string;
  source_type: string;
  architecture: string;
  file_size_bytes: number;
  description: string;
  preview_image_path: string | null;
  supported_resolutions: [number, number][];
  available: boolean;
  loaded: boolean;
  created_at: string;
}

export interface LoraInfo {
  id: number;
  name: string;
  filename: string;
  file_size_bytes: number;
  base_architecture: string;
  rank: number | null;
  enabled: boolean;
  default_strength: number;
  trigger_words: string;
  description: string;
  preview_image_path: string | null;
  available: boolean;
  created_at: string;
}

export type LoraUpdate = Partial<
  Pick<LoraInfo, "name" | "enabled" | "default_strength" | "trigger_words" | "description">
>;

export interface GenerateRequest {
  model_id: number;
  prompt: string;
  negative_prompt: string;
  lora_id: number | null;
  lora_strength: number;
  width: number;
  height: number;
  steps: number;
  guidance_scale: number;
  seed: number | null;
  num_images: number;
}

export type JobStatus = "queued" | "running" | "completed" | "failed" | "cancelled";

export interface Job {
  id: string;
  kind: string;
  status: JobStatus;
  step: number;
  total_steps: number;
  message: string;
  created_at: number;
  started_at: number | null;
  finished_at: number | null;
  result: { generation_id?: number; comparison_id?: number } | null;
  error: { code: string; message: string } | null;
}

export interface GenerationImage {
  id: number;
  index: number;
  seed: number;
  width: number;
  height: number;
  file_size_bytes: number;
  /** The model's safety checker replaced this image with a black frame. */
  safety_blocked: boolean;
  url: string;
}

export interface Generation {
  id: number;
  created_at: string;
  prompt: string;
  negative_prompt: string;
  model_id: number | null;
  model_name: string;
  lora_id: number | null;
  lora_name: string | null;
  lora_strength: number | null;
  seed: number;
  width: number;
  height: number;
  steps: number;
  guidance_scale: number;
  num_images: number;
  duration_ms: number;
  device: string;
  pipeline_config: Record<string, unknown>;
  comparison_id: number | null;
  comparison_index: number | null;
  images: GenerationImage[];
}

export interface HistoryPage {
  items: Generation[];
  total: number;
  page: number;
  page_size: number;
}

export interface HistoryQuery {
  q?: string;
  model_id?: number;
  lora_id?: number;
  sort?: "newest" | "oldest";
  page?: number;
  page_size?: number;
}

export interface SystemInfo {
  torch_installed: boolean;
  torch_version: string | null;
  cuda_available: boolean;
  cuda_version: string | null;
  gpu_name: string | null;
  vram_total_bytes: number | null;
  vram_used_bytes: number | null;
  vram_free_bytes: number | null;
  device: string;
  generation_backend: string;
  cpu_percent: number;
  cpu_count: number | null;
  ram_total_bytes: number;
  ram_used_bytes: number;
  ram_available_bytes: number;
  disk_total_bytes: number;
  disk_used_bytes: number;
  disk_free_bytes: number;
}

export interface GenerationDefaults {
  negative_prompt: string;
  width: number;
  height: number;
  steps: number;
  guidance_scale: number;
  num_images: number;
}

export interface AppSettings {
  runtime: {
    model_directory: string;
    lora_directory: string;
    output_directory: string;
    dataset_directory: string;
    device: string;
    generation_backend: string;
    enable_cpu_offload: boolean;
    model_idle_unload_seconds: number;
    max_upload_size_mb: number;
  };
  generation_defaults: GenerationDefaults;
}

export type CompareAxisKind = "lora_strength" | "seed" | "model";

/** One value per cell. `null` in a LoRA-strength comparison means "without the LoRA". */
export type CompareAxis =
  | { kind: "lora_strength"; values: (number | null)[] }
  | { kind: "seed"; values: number[] }
  | { kind: "model"; values: number[] };

export interface CompareRequest {
  axis: CompareAxis;
  prompt: string;
  negative_prompt: string;
  model_id: number | null;
  lora_id: number | null;
  lora_strength: number;
  width: number;
  height: number;
  steps: number;
  guidance_scale: number;
  seed: number | null;
}

export type ComparisonStatus = "running" | "completed" | "cancelled" | "failed" | "interrupted";

export interface ComparisonSummary {
  id: number;
  created_at: string;
  prompt: string;
  axis: CompareAxisKind;
  axis_values: (number | null)[];
  status: ComparisonStatus;
  error_message: string | null;
}

export interface Comparison extends ComparisonSummary {
  cells: Generation[];
}

export type QualityFlag =
  "low_resolution" | "extreme_aspect_ratio" | "possibly_blurry" | "near_duplicate";

export interface DatasetImage {
  id: number;
  dataset_id: number;
  position: number;
  original_filename: string;
  format: string;
  width: number;
  height: number;
  file_size_bytes: number;
  blur_score: number;
  caption: string;
  /** "manual" today; AI captioning will add another source. */
  caption_source: string | null;
  caption_updated_at: string | null;
  created_at: string;
  flags: QualityFlag[];
  near_duplicate_of: number[];
  url: string;
  thumbnail_url: string;
}

export interface DatasetSummary {
  id: number;
  name: string;
  description: string;
  target_resolution: number;
  created_at: string;
  updated_at: string;
  image_count: number;
  flagged_count: number;
  uncaptioned_count: number;
  cover_thumbnail_url: string | null;
}

export interface Dataset extends DatasetSummary {
  images: DatasetImage[];
}

export interface DatasetInput {
  name: string;
  description: string;
  target_resolution: number;
}

export interface SkippedUpload {
  filename: string;
  reason: string;
  message: string;
}

export interface UploadResult {
  added: DatasetImage[];
  skipped: SkippedUpload[];
}
