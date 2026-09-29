"use client";

import { useEffect, useState } from "react";
import { RefreshCw } from "lucide-react";
import { LoraCard } from "@/components/loras/LoraCard";
import { LoraImport } from "@/components/loras/LoraImport";
import { Button, EmptyState, ErrorBanner, PageHeader } from "@/components/ui/primitives";
import { api, errorMessage } from "@/lib/api";
import type { LoraInfo } from "@/lib/types";

export default function LorasPage() {
  const [loras, setLoras] = useState<LoraInfo[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [rescanning, setRescanning] = useState(false);

  useEffect(() => {
    api.listLoras().then(setLoras, (err: unknown) => setError(errorMessage(err)));
  }, []);

  async function rescan() {
    setRescanning(true);
    setError(null);
    try {
      setLoras(await api.rescanLoras());
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setRescanning(false);
    }
  }

  function replace(updated: LoraInfo) {
    setLoras((current) => current?.map((l) => (l.id === updated.id ? updated : l)) ?? null);
  }

  return (
    <div className="mx-auto max-w-[1100px]">
      <PageHeader
        title="LoRAs"
        description="Adapters are validated on import and only offered for compatible base models."
        actions={
          <Button onClick={() => void rescan()} disabled={rescanning}>
            <RefreshCw aria-hidden className={`size-4 ${rescanning ? "animate-spin" : ""}`} />
            Rescan
          </Button>
        }
      />
      <div className="space-y-4">
        <LoraImport onImported={(lora) => setLoras((current) => [...(current ?? []), lora])} />
        <ErrorBanner message={error} />
        {loras?.length === 0 && (
          <EmptyState title="No LoRAs yet">
            Import a .safetensors LoRA adapter to get started.
          </EmptyState>
        )}
        {loras?.map((lora) => (
          <LoraCard
            key={lora.id}
            lora={lora}
            onUpdated={replace}
            onDeleted={(id) => setLoras((current) => current?.filter((l) => l.id !== id) ?? null)}
          />
        ))}
      </div>
    </div>
  );
}
