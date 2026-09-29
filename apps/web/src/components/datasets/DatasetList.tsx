"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { EmptyState, ErrorBanner, PageHeader, Panel } from "@/components/ui/primitives";
import { api, errorMessage, imageUrl } from "@/lib/api";
import { formatDate } from "@/lib/format";
import type { DatasetInput, DatasetSummary } from "@/lib/types";
import { DatasetForm } from "./DatasetForm";

export function DatasetList() {
  const router = useRouter();
  const [datasets, setDatasets] = useState<DatasetSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.listDatasets().then(setDatasets, (err: unknown) => setError(errorMessage(err)));
  }, []);

  async function create(input: DatasetInput): Promise<boolean> {
    try {
      const dataset = await api.createDataset(input);
      router.push(`/datasets/${dataset.id}`);
      return true;
    } catch (err) {
      setError(errorMessage(err));
      return false;
    }
  }

  return (
    <div className="mx-auto max-w-[1100px] space-y-4">
      <PageHeader
        title="Datasets"
        description="Collect and caption training images for future LoRA training."
      />
      <ErrorBanner message={error} />
      <Panel title="New dataset">
        <DatasetForm idPrefix="new-dataset" submitLabel="Create dataset" onSubmit={create} />
      </Panel>
      {datasets?.length === 0 && (
        <EmptyState title="No datasets yet">Create one above to start adding images.</EmptyState>
      )}
      <ul aria-label="Datasets" className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        {datasets?.map((dataset) => (
          <li key={dataset.id}>
            <Link
              href={`/datasets/${dataset.id}`}
              className="border-line bg-panel hover:border-faint grid grid-cols-[72px_1fr] gap-3 rounded-lg border p-3"
            >
              {dataset.cover_thumbnail_url ? (
                // eslint-disable-next-line @next/next/no-img-element -- next/image refuses local-IP sources
                <img
                  src={imageUrl(dataset.cover_thumbnail_url)}
                  alt=""
                  className="bg-raised aspect-square w-full rounded-md object-cover"
                />
              ) : (
                <div className="bg-raised aspect-square rounded-md" />
              )}
              <div className="min-w-0">
                <p className="truncate font-medium">{dataset.name}</p>
                <p className="text-muted text-xs">
                  {dataset.image_count} image{dataset.image_count === 1 ? "" : "s"} ·{" "}
                  {dataset.flagged_count} flagged · {dataset.uncaptioned_count} uncaptioned
                </p>
                <p className="text-faint mt-1 text-xs">
                  {dataset.target_resolution} px · updated {formatDate(dataset.updated_at)}
                </p>
              </div>
            </Link>
          </li>
        ))}
      </ul>
    </div>
  );
}
