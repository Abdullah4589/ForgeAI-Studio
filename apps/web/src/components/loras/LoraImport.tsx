"use client";

import { useRef, useState } from "react";
import { Upload } from "lucide-react";
import { Button, ErrorBanner, inputClass, Panel } from "@/components/ui/primitives";
import { api, errorMessage } from "@/lib/api";
import type { LoraInfo } from "@/lib/types";

export function LoraImport({ onImported }: { onImported: (lora: LoraInfo) => void }) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  async function upload() {
    if (!file) return;
    if (!file.name.toLowerCase().endsWith(".safetensors")) {
      setError("Only .safetensors files can be imported.");
      return;
    }
    setBusy(true);
    setError(null);
    setMessage(null);
    try {
      const lora = await api.importLora(file);
      onImported(lora);
      setMessage(`Imported ${lora.filename}.`);
      setFile(null);
      if (inputRef.current) inputRef.current.value = "";
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Panel title="Import LoRA">
      <div className="flex flex-wrap items-end gap-3">
        <div className="min-w-60 flex-1">
          <label htmlFor="lora-file" className="text-muted mb-1 block text-xs font-medium">
            LoRA file (.safetensors)
          </label>
          <input
            ref={inputRef}
            id="lora-file"
            type="file"
            accept=".safetensors"
            onChange={(event) => setFile(event.target.files?.[0] ?? null)}
            className={`${inputClass} file:bg-raised file:text-ink file:mr-3 file:rounded file:border-0 file:px-2 file:py-1`}
          />
        </div>
        <Button variant="primary" onClick={() => void upload()} disabled={!file || busy}>
          <Upload aria-hidden className="size-4" />
          {busy ? "Importing…" : "Import"}
        </Button>
      </div>
      <div className="mt-3 space-y-2">
        <ErrorBanner message={error} />
        {message && (
          <p role="status" className="text-ok text-sm">
            {message}
          </p>
        )}
      </div>
    </Panel>
  );
}
