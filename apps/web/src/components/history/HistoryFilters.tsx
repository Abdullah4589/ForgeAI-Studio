import { Search } from "lucide-react";
import { inputClass } from "@/components/ui/primitives";
import type { HistoryQuery, LoraInfo, ModelInfo } from "@/lib/types";

interface HistoryFiltersProps {
  query: HistoryQuery;
  models: ModelInfo[];
  loras: LoraInfo[];
  onChange: (query: HistoryQuery) => void;
}

function toId(value: string): number | undefined {
  return value ? Number(value) : undefined;
}

export function HistoryFilters({ query, models, loras, onChange }: HistoryFiltersProps) {
  return (
    <div
      role="search"
      className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-[1fr_200px_200px_160px]"
    >
      <div className="relative">
        <label htmlFor="history-search" className="sr-only">
          Search prompts
        </label>
        <Search
          aria-hidden
          className="text-faint pointer-events-none absolute top-2.5 left-3 size-4"
        />
        <input
          id="history-search"
          type="search"
          placeholder="Search prompts"
          value={query.q ?? ""}
          onChange={(event) => onChange({ ...query, q: event.target.value, page: 1 })}
          className={`${inputClass} pl-9`}
        />
      </div>
      <FilterSelect
        id="history-model"
        label="Filter by model"
        value={query.model_id}
        options={models.map((m) => ({ value: m.id, label: m.name }))}
        allLabel="All models"
        onChange={(value) => onChange({ ...query, model_id: toId(value), page: 1 })}
      />
      <FilterSelect
        id="history-lora"
        label="Filter by LoRA"
        value={query.lora_id}
        options={loras.map((l) => ({ value: l.id, label: l.name }))}
        allLabel="All LoRAs"
        onChange={(value) => onChange({ ...query, lora_id: toId(value), page: 1 })}
      />
      <div>
        <label htmlFor="history-sort" className="sr-only">
          Sort order
        </label>
        <select
          id="history-sort"
          value={query.sort ?? "newest"}
          onChange={(event) =>
            onChange({ ...query, sort: event.target.value as "newest" | "oldest", page: 1 })
          }
          className={inputClass}
        >
          <option value="newest">Newest first</option>
          <option value="oldest">Oldest first</option>
        </select>
      </div>
    </div>
  );
}

function FilterSelect({
  id,
  label,
  value,
  options,
  allLabel,
  onChange,
}: {
  id: string;
  label: string;
  value: number | undefined;
  options: { value: number; label: string }[];
  allLabel: string;
  onChange: (value: string) => void;
}) {
  return (
    <div>
      <label htmlFor={id} className="sr-only">
        {label}
      </label>
      <select
        id={id}
        value={value === undefined ? "" : String(value)}
        onChange={(event) => onChange(event.target.value)}
        className={inputClass}
      >
        <option value="">{allLabel}</option>
        {options.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
    </div>
  );
}
