"use client";

import { useEffect, useState } from "react";
import { Button, EmptyState, ErrorBanner, PageHeader } from "@/components/ui/primitives";
import { api, errorMessage } from "@/lib/api";
import type { Generation, HistoryPage, HistoryQuery, LoraInfo, ModelInfo } from "@/lib/types";
import { HistoryFilters } from "./HistoryFilters";
import { HistoryItem } from "./HistoryItem";

const PAGE_SIZE = 20;
const SEARCH_DEBOUNCE_MS = 250;

export function HistoryBrowser() {
  const [query, setQuery] = useState<HistoryQuery>({ sort: "newest", page: 1 });
  const [page, setPage] = useState<HistoryPage | null>(null);
  const [models, setModels] = useState<ModelInfo[]>([]);
  const [loras, setLoras] = useState<LoraInfo[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    Promise.all([api.listModels(), api.listLoras()]).then(
      ([modelList, loraList]) => {
        setModels(modelList);
        setLoras(loraList);
      },
      (err: unknown) => setError(errorMessage(err)),
    );
  }, []);

  useEffect(() => {
    let cancelled = false;
    const timer = setTimeout(() => {
      api.listHistory({ ...query, page_size: PAGE_SIZE }).then(
        (result) => {
          if (!cancelled) {
            setPage(result);
            setError(null);
          }
        },
        (err: unknown) => !cancelled && setError(errorMessage(err)),
      );
    }, SEARCH_DEBOUNCE_MS);
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [query, reloadKey]);

  async function remove(generation: Generation) {
    try {
      await api.deleteGeneration(generation.id);
      setReloadKey((key) => key + 1);
    } catch (err) {
      setError(errorMessage(err));
    }
  }

  const totalPages = page ? Math.max(1, Math.ceil(page.total / PAGE_SIZE)) : 1;
  const current = query.page ?? 1;

  return (
    <div className="mx-auto max-w-[1100px]">
      <PageHeader
        title="History"
        description="Every generation is saved with its full settings so it can be reproduced."
      />
      <HistoryFilters query={query} models={models} loras={loras} onChange={setQuery} />
      <div className="mt-4 space-y-3">
        <ErrorBanner message={error} />
        {page && (
          <p className="text-muted text-xs" aria-live="polite">
            {page.total} generation{page.total === 1 ? "" : "s"}
          </p>
        )}
        {page?.items.length === 0 && (
          <EmptyState title="No generations found">
            Try a different search, or create something on the Generate page.
          </EmptyState>
        )}
        <div className="space-y-3">
          {page?.items.map((generation) => (
            <HistoryItem key={generation.id} generation={generation} onDelete={remove} />
          ))}
        </div>
        {totalPages > 1 && (
          <nav aria-label="Pagination" className="flex items-center justify-center gap-3 pt-2">
            <Button
              disabled={current <= 1}
              onClick={() => setQuery({ ...query, page: current - 1 })}
            >
              Previous
            </Button>
            <span className="text-muted text-sm tabular-nums">
              Page {current} of {totalPages}
            </span>
            <Button
              disabled={current >= totalPages}
              onClick={() => setQuery({ ...query, page: current + 1 })}
            >
              Next
            </Button>
          </nav>
        )}
      </div>
    </div>
  );
}
