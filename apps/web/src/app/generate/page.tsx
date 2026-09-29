import { GenerateWorkspace } from "@/components/generate/GenerateWorkspace";

export default async function GeneratePage({ searchParams }: PageProps<"/generate">) {
  const params = await searchParams;
  const from = typeof params.from === "string" ? Number.parseInt(params.from, 10) : NaN;
  return (
    <GenerateWorkspace
      fromGenerationId={Number.isFinite(from) ? from : null}
      autoRun={params.run === "1"}
    />
  );
}
