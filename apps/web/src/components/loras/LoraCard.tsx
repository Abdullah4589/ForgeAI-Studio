"use client";

import { useState } from "react";
import { Trash2 } from "lucide-react";
import { Badge, Button, ErrorBanner, inputClass, Panel } from "@/components/ui/primitives";
import { api, errorMessage } from "@/lib/api";
import { architectureLabel, formatBytes } from "@/lib/format";
import type { LoraInfo } from "@/lib/types";

interface LoraCardProps {
  lora: LoraInfo;
  onUpdated: (lora: LoraInfo) => void;
  onDeleted: (id: number) => void;
}

export function LoraCard({ lora, onUpdated, onDeleted }: LoraCardProps) {
  const [draft, setDraft] = useState({
    name: lora.name,
    trigger_words: lora.trigger_words,
    description: lora.description,
    default_strength: lora.default_strength,
  });
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const idPrefix = `lora-${lora.id}`;
  const dirty =
    draft.name !== lora.name ||
    draft.trigger_words !== lora.trigger_words ||
    draft.description !== lora.description ||
    draft.default_strength !== lora.default_strength;

  async function save(changes: Parameters<typeof api.updateLora>[1]) {
    setSaving(true);
    setError(null);
    try {
      onUpdated(await api.updateLora(lora.id, changes));
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setSaving(false);
    }
  }

  async function remove() {
    try {
      await api.deleteLora(lora.id);
      onDeleted(lora.id);
    } catch (err) {
      setError(errorMessage(err));
    }
  }

  return (
    <Panel>
      <article aria-label={`LoRA ${lora.name}`}>
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="min-w-0">
            <h2 className="font-medium">{lora.name}</h2>
            <p className="text-faint font-mono text-xs">{lora.filename}</p>
            <div className="mt-2 flex flex-wrap gap-1.5">
              <Badge tone={lora.base_architecture === "unknown" ? "warn" : "neutral"}>
                For {architectureLabel(lora.base_architecture)}
              </Badge>
              {lora.rank !== null && <Badge>rank {lora.rank}</Badge>}
              <Badge>{formatBytes(lora.file_size_bytes)}</Badge>
              {!lora.available && <Badge tone="warn">File missing</Badge>}
            </div>
          </div>
          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={lora.enabled}
              disabled={saving}
              onChange={(event) => void save({ enabled: event.target.checked })}
              className="size-4 accent-[var(--color-accent)]"
            />
            Enabled
          </label>
        </div>

        <div className="mt-4 grid grid-cols-1 gap-3 md:grid-cols-2">
          <TextInput
            id={`${idPrefix}-name`}
            label="Name"
            value={draft.name}
            onChange={(name) => setDraft({ ...draft, name })}
          />
          <TextInput
            id={`${idPrefix}-triggers`}
            label="Trigger words"
            value={draft.trigger_words}
            onChange={(trigger_words) => setDraft({ ...draft, trigger_words })}
          />
          <TextInput
            id={`${idPrefix}-description`}
            label="Description"
            value={draft.description}
            onChange={(description) => setDraft({ ...draft, description })}
          />
          <div>
            <div className="mb-1 flex justify-between">
              <label htmlFor={`${idPrefix}-strength`} className="text-muted text-xs font-medium">
                Default strength
              </label>
              <span className="font-mono text-xs tabular-nums">
                {draft.default_strength.toFixed(2)}
              </span>
            </div>
            <input
              id={`${idPrefix}-strength`}
              type="range"
              min={-2}
              max={2}
              step={0.05}
              value={draft.default_strength}
              onChange={(event) =>
                setDraft({ ...draft, default_strength: Number(event.target.value) })
              }
              className="w-full"
            />
          </div>
        </div>

        <div className="mt-4 flex flex-wrap items-center gap-2">
          <Button variant="primary" disabled={!dirty || saving} onClick={() => void save(draft)}>
            Save
          </Button>
          {confirming ? (
            <>
              <Button variant="danger" onClick={() => void remove()}>
                Confirm delete
              </Button>
              <Button variant="ghost" onClick={() => setConfirming(false)}>
                Keep
              </Button>
            </>
          ) : (
            <Button variant="ghost" onClick={() => setConfirming(true)}>
              <Trash2 aria-hidden className="size-4" />
              Delete
            </Button>
          )}
        </div>
        <div className="mt-2">
          <ErrorBanner message={error} />
        </div>
      </article>
    </Panel>
  );
}

function TextInput({
  id,
  label,
  value,
  onChange,
}: {
  id: string;
  label: string;
  value: string;
  onChange: (value: string) => void;
}) {
  return (
    <div>
      <label htmlFor={id} className="text-muted mb-1 block text-xs font-medium">
        {label}
      </label>
      <input
        id={id}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className={inputClass}
      />
    </div>
  );
}
