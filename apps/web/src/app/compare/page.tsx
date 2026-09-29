import { CompareWorkspace } from "@/components/compare/CompareWorkspace";

export default async function ComparePage({ searchParams }: PageProps<"/compare">) {
  const params = await searchParams;
  const id = typeof params.id === "string" ? Number.parseInt(params.id, 10) : NaN;
  return <CompareWorkspace comparisonId={Number.isFinite(id) ? id : null} />;
}
