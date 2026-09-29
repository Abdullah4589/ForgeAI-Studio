import Link from "next/link";
import { Panel } from "@/components/ui/primitives";
import { AXIS_LABELS, cellLabel } from "@/lib/compare-form";
import { formatDate } from "@/lib/format";
import type { ComparisonSummary, ModelInfo } from "@/lib/types";

interface RecentComparisonsProps {
  comparisons: ComparisonSummary[];
  models: ModelInfo[];
  activeId: number | null;
}

export function RecentComparisons({ comparisons, models, activeId }: RecentComparisonsProps) {
  if (comparisons.length === 0) return null;
  return (
    <Panel title="Recent comparisons">
      <ul className="divide-line divide-y">
        {comparisons.map((comparison) => (
          <li key={comparison.id}>
            <Link
              href={`/compare?id=${comparison.id}`}
              aria-current={comparison.id === activeId ? "true" : undefined}
              className="hover:bg-raised aria-[current=true]:bg-raised block rounded-md px-2 py-2"
            >
              <span className="line-clamp-1 text-sm">{comparison.prompt}</span>
              <span className="text-faint block text-xs">
                {AXIS_LABELS[comparison.axis]}:{" "}
                {comparison.axis_values
                  .map((v) => cellLabel(comparison.axis, v, models))
                  .join(" | ")}
                {" · "}
                {formatDate(comparison.created_at)} · {comparison.status}
              </span>
            </Link>
          </li>
        ))}
      </ul>
    </Panel>
  );
}
