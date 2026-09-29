import { notFound } from "next/navigation";
import { DatasetWorkspace } from "@/components/datasets/DatasetWorkspace";

export default async function DatasetPage({ params }: PageProps<"/datasets/[id]">) {
  const { id } = await params;
  const datasetId = Number.parseInt(id, 10);
  if (!Number.isFinite(datasetId)) notFound();
  return <DatasetWorkspace datasetId={datasetId} />;
}
