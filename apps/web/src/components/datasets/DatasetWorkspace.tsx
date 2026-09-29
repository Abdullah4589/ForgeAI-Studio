"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { ArrowLeft, Trash2 } from "lucide-react";
import {
  Button,
  EmptyState,
  ErrorBanner,
  inputClass,
  PageHeader,
  Panel,
} from "@/components/ui/primitives";
import { api, errorMessage } from "@/lib/api";
import {
  batches,
  filterImages,
  mergeUploadResults,
  moveItem,
  uploadSummary,
  type ImageFilter,
} from "@/lib/datasets";
import type { Dataset, DatasetImage, DatasetInput, UploadResult } from "@/lib/types";
import { DatasetForm } from "./DatasetForm";
import { DatasetImageCard } from "./DatasetImageCard";
import { ImagePreviewDialog } from "./ImagePreviewDialog";
import { UploadDropzone } from "./UploadDropzone";

export function DatasetWorkspace({ datasetId }: { datasetId: number }) {
  const router = useRouter();
  const [dataset, setDataset] = useState<Dataset | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const [report, setReport] = useState<UploadResult | null>(null);
  const [filter, setFilter] = useState<ImageFilter>("all");
  const [preview, setPreview] = useState<DatasetImage | null>(null);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const dragFrom = useRef<number | null>(null);

  useEffect(() => {
    let stale = false;
    api.getDataset(datasetId).then(
      (loaded) => {
        if (!stale) setDataset(loaded);
      },
      (err: unknown) => {
        if (!stale) setError(errorMessage(err));
      },
    );
    return () => {
      stale = true;
    };
  }, [datasetId]);

  async function refresh() {
    setDataset(await api.getDataset(datasetId));
  }

  async function upload(files: File[]) {
    setUploading(true);
    setError(null);
    setReport(null);
    const results: UploadResult[] = [];
    try {
      // The API accepts a limited number of files per request.
      for (const batch of batches(files)) {
        results.push(await api.uploadDatasetImages(datasetId, batch));
      }
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setReport(mergeUploadResults(results));
      await refresh().catch((err: unknown) => setError(errorMessage(err)));
      setUploading(false);
    }
  }

  async function saveCaption(image: DatasetImage, caption: string): Promise<boolean> {
    try {
      const updated = await api.updateCaption(datasetId, image.id, caption);
      setDataset((current) =>
        current
          ? {
              ...current,
              images: current.images.map((i) => (i.id === updated.id ? updated : i)),
              uncaptioned_count: current.images.filter((i) =>
                i.id === updated.id ? !updated.caption : !i.caption,
              ).length,
            }
          : current,
      );
      return true;
    } catch (err) {
      setError(errorMessage(err));
      return false;
    }
  }

  async function move(from: number, to: number) {
    if (!dataset) return;
    const previous = dataset;
    const images = moveItem(dataset.images, from, to);
    if (images === dataset.images) return;
    // Optimistic: reorder immediately, then keep the server's version (or roll back on error).
    setDataset({ ...dataset, images });
    try {
      setDataset(
        await api.reorderDataset(
          datasetId,
          images.map((image) => image.id),
        ),
      );
    } catch (err) {
      setDataset(previous);
      setError(errorMessage(err));
    }
  }

  async function remove(image: DatasetImage) {
    try {
      await api.deleteDatasetImage(datasetId, image.id);
      await refresh();
    } catch (err) {
      setError(errorMessage(err));
    }
  }

  async function saveSettings(input: DatasetInput): Promise<boolean> {
    try {
      setDataset(await api.updateDataset(datasetId, input));
      return true;
    } catch (err) {
      setError(errorMessage(err));
      return false;
    }
  }

  async function deleteDataset() {
    try {
      await api.deleteDataset(datasetId);
      router.push("/datasets");
    } catch (err) {
      setError(errorMessage(err));
    }
  }

  if (!dataset) {
    return (
      <div className="mx-auto max-w-[1400px]">
        <ErrorBanner message={error} />
      </div>
    );
  }

  const visible = filterImages(dataset.images, filter);
  const canReorder = filter === "all";
  const nameOf = (id: number) =>
    dataset.images.find((image) => image.id === id)?.original_filename ?? `#${id}`;

  return (
    <div className="mx-auto max-w-[1400px] space-y-4">
      <Link
        href="/datasets"
        className="text-muted hover:text-ink inline-flex items-center gap-1 text-sm"
      >
        <ArrowLeft aria-hidden className="size-4" />
        All datasets
      </Link>
      <PageHeader title={dataset.name} description={dataset.description || undefined} />
      <p className="text-muted text-sm" aria-label="Dataset summary">
        {dataset.image_count} image{dataset.image_count === 1 ? "" : "s"} · {dataset.flagged_count}{" "}
        flagged · {dataset.uncaptioned_count} uncaptioned · target {dataset.target_resolution} px
      </p>
      <ErrorBanner message={error} />

      <Panel title="Add images">
        <UploadDropzone busy={uploading} onFiles={(files) => void upload(files)} />
        {report && (
          <div className="mt-3 text-sm" aria-label="Upload report">
            <p role="status">{uploadSummary(report)}</p>
            {report.skipped.length > 0 && (
              <ul className="text-muted mt-1 list-inside list-disc text-xs">
                {report.skipped.map((skip, index) => (
                  <li key={`${skip.filename}-${index}`}>
                    <span className="text-ink">{skip.filename}</span>: {skip.message}
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}
      </Panel>

      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <label htmlFor="image-filter" className="text-muted mb-1 block text-xs font-medium">
            Show
          </label>
          <select
            id="image-filter"
            value={filter}
            onChange={(event) => setFilter(event.target.value as ImageFilter)}
            className={`${inputClass} w-48`}
          >
            <option value="all">All images</option>
            <option value="flagged">Flagged only</option>
            <option value="uncaptioned">Uncaptioned only</option>
          </select>
        </div>
        <p className="text-faint text-xs">
          {canReorder
            ? "Drag images or use the arrows to change the order."
            : "Show all images to change the order."}
        </p>
      </div>

      {dataset.images.length === 0 ? (
        <EmptyState title="No images yet">
          Add images above to start building the dataset.
        </EmptyState>
      ) : visible.length === 0 ? (
        <EmptyState title="Nothing to show">No images match this filter.</EmptyState>
      ) : (
        <ul
          aria-label="Dataset images"
          className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4"
        >
          {visible.map((image, index) => (
            <DatasetImageCard
              key={image.id}
              image={image}
              index={canReorder ? index : dataset.images.indexOf(image)}
              total={dataset.images.length}
              canReorder={canReorder}
              nameOf={nameOf}
              onPreview={setPreview}
              onMove={(from, to) => void move(from, to)}
              onSaveCaption={saveCaption}
              onRemove={(target) => void remove(target)}
              dragHandlers={{
                onDragStart: () => {
                  dragFrom.current = index;
                },
                onDragOver: (event) => {
                  if (canReorder) event.preventDefault();
                },
                onDrop: () => {
                  if (dragFrom.current !== null) void move(dragFrom.current, index);
                  dragFrom.current = null;
                },
                onDragEnd: () => {
                  dragFrom.current = null;
                },
              }}
            />
          ))}
        </ul>
      )}

      <details className="border-line bg-panel rounded-lg border p-4">
        <summary className="cursor-pointer text-sm font-semibold">Dataset settings</summary>
        <div className="mt-3">
          <DatasetForm
            idPrefix="edit-dataset"
            submitLabel="Save settings"
            initial={{
              name: dataset.name,
              description: dataset.description,
              target_resolution: dataset.target_resolution,
            }}
            onSubmit={saveSettings}
          />
          <div className="border-line mt-4 border-t pt-4">
            {confirmDelete ? (
              <div className="flex flex-wrap items-center gap-2">
                <span className="text-sm">Delete this dataset and all its image files?</span>
                <Button variant="danger" onClick={() => void deleteDataset()}>
                  Delete dataset
                </Button>
                <Button variant="ghost" onClick={() => setConfirmDelete(false)}>
                  Keep
                </Button>
              </div>
            ) : (
              <Button variant="ghost" onClick={() => setConfirmDelete(true)}>
                <Trash2 aria-hidden className="size-4" />
                Delete dataset…
              </Button>
            )}
          </div>
        </div>
      </details>

      {preview && <ImagePreviewDialog image={preview} onClose={() => setPreview(null)} />}
    </div>
  );
}
