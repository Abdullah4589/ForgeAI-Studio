import type {
  AppSettings,
  CaptionJob,
  CaptionRequest,
  CompareRequest,
  Comparison,
  ComparisonSummary,
  Dataset,
  DatasetImage,
  DatasetInput,
  DatasetSummary,
  Generation,
  GenerationDefaults,
  GenerateRequest,
  HistoryPage,
  HistoryQuery,
  Job,
  LoraInfo,
  LoraUpdate,
  ModelInfo,
  SystemInfo,
  TrainingJob,
  TrainingRequest,
  TrainingRun,
  UploadResult,
} from "./types";

export const API_URL = (process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000").replace(
  /\/$/,
  "",
);

export interface FieldError {
  field: string;
  message: string;
}

/** Error thrown for any non-2xx API response, carrying the server's user-safe message. */
export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
    readonly code: string,
    readonly fields: FieldError[] = [],
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_URL}${path}`, init);
  } catch {
    throw new ApiError(
      `Cannot reach the ForgeAI API at ${API_URL}. Is the backend running?`,
      0,
      "network_error",
    );
  }
  if (response.status === 204) {
    return undefined as T;
  }
  const body: unknown = await response.json().catch(() => null);
  if (!response.ok) {
    const error = (body as { error?: { code?: string; message?: string; fields?: FieldError[] } })
      ?.error;
    throw new ApiError(
      error?.message ?? `Request failed (${response.status}).`,
      response.status,
      error?.code ?? "unknown_error",
      error?.fields ?? [],
    );
  }
  return body as T;
}

function json(method: string, body: unknown): RequestInit {
  return { method, headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) };
}

export function imageUrl(path: string, download = false): string {
  return `${API_URL}${path}${download ? "?download=true" : ""}`;
}

export const api = {
  listModels: () => request<ModelInfo[]>("/api/models"),
  rescanModels: () => request<ModelInfo[]>("/api/models/rescan", { method: "POST" }),
  loadModel: (modelId: number) =>
    request<{ loaded_model_id: number | null }>(
      "/api/models/load",
      json("POST", { model_id: modelId }),
    ),
  unloadModel: () =>
    request<{ loaded_model_id: number | null }>("/api/models/unload", { method: "POST" }),

  listLoras: () => request<LoraInfo[]>("/api/loras"),
  rescanLoras: () => request<LoraInfo[]>("/api/loras/rescan", { method: "POST" }),
  importLora: (file: File) => {
    const form = new FormData();
    form.append("file", file);
    return request<LoraInfo>("/api/loras/import", { method: "POST", body: form });
  },
  updateLora: (id: number, changes: LoraUpdate) =>
    request<LoraInfo>(`/api/loras/${id}`, json("PATCH", changes)),
  deleteLora: (id: number) => request<void>(`/api/loras/${id}`, { method: "DELETE" }),

  generate: (body: GenerateRequest) => request<Job>("/api/generate", json("POST", body)),
  cancelGeneration: (jobId: string) =>
    request<Job>("/api/generate/cancel", json("POST", { job_id: jobId })),
  getJob: (jobId: string) => request<Job>(`/api/jobs/${jobId}`),
  jobEventsUrl: (jobId: string) => `${API_URL}/api/jobs/${jobId}/events`,

  listHistory: (query: HistoryQuery = {}) => {
    const params = new URLSearchParams();
    for (const [key, value] of Object.entries(query)) {
      if (value !== undefined && value !== "") params.set(key, String(value));
    }
    const qs = params.toString();
    return request<HistoryPage>(`/api/history${qs ? `?${qs}` : ""}`);
  },
  getGeneration: (id: number) => request<Generation>(`/api/history/${id}`),
  deleteGeneration: (id: number) => request<void>(`/api/history/${id}`, { method: "DELETE" }),
  deleteImage: (id: number) => request<void>(`/api/history/images/${id}`, { method: "DELETE" }),

  compare: (body: CompareRequest) =>
    request<Job & { comparison_id: number }>("/api/compare", json("POST", body)),
  listComparisons: (limit = 20) => request<ComparisonSummary[]>(`/api/comparisons?limit=${limit}`),
  getComparison: (id: number) => request<Comparison>(`/api/comparisons/${id}`),
  deleteComparison: (id: number) => request<void>(`/api/comparisons/${id}`, { method: "DELETE" }),

  listDatasets: () => request<DatasetSummary[]>("/api/datasets"),
  createDataset: (body: DatasetInput) => request<Dataset>("/api/datasets", json("POST", body)),
  getDataset: (id: number) => request<Dataset>(`/api/datasets/${id}`),
  updateDataset: (id: number, changes: Partial<DatasetInput>) =>
    request<Dataset>(`/api/datasets/${id}`, json("PATCH", changes)),
  deleteDataset: (id: number) => request<void>(`/api/datasets/${id}`, { method: "DELETE" }),
  uploadDatasetImages: (id: number, files: File[]) => {
    const form = new FormData();
    for (const file of files) form.append("files", file);
    return request<UploadResult>(`/api/datasets/${id}/images`, { method: "POST", body: form });
  },
  updateCaption: (datasetId: number, imageId: number, caption: string) =>
    request<DatasetImage>(
      `/api/datasets/${datasetId}/images/${imageId}`,
      json("PATCH", { caption }),
    ),
  deleteDatasetImage: (datasetId: number, imageId: number) =>
    request<void>(`/api/datasets/${datasetId}/images/${imageId}`, { method: "DELETE" }),
  generateCaptions: (datasetId: number, body: CaptionRequest) =>
    request<CaptionJob>(`/api/datasets/${datasetId}/captions`, json("POST", body)),
  reorderDataset: (id: number, imageIds: number[]) =>
    request<Dataset>(`/api/datasets/${id}/order`, json("PUT", { image_ids: imageIds })),

  startTraining: (body: TrainingRequest) =>
    request<TrainingJob>("/api/training", json("POST", body)),
  listTrainingRuns: (limit = 20) => request<TrainingRun[]>(`/api/training?limit=${limit}`),
  getTrainingRun: (id: number) => request<TrainingRun>(`/api/training/${id}`),
  deleteTrainingRun: (id: number) => request<void>(`/api/training/${id}`, { method: "DELETE" }),

  getSystem: () => request<SystemInfo>("/api/system"),
  getSettings: () => request<AppSettings>("/api/settings"),
  saveGenerationDefaults: (defaults: GenerationDefaults) =>
    request<GenerationDefaults>("/api/settings/generation-defaults", json("PUT", defaults)),
};

export function errorMessage(error: unknown): string {
  if (error instanceof ApiError) return error.message;
  return "Something went wrong. Please try again.";
}
