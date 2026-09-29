"use client";

import { useRef, useState } from "react";
import { ImagePlus } from "lucide-react";
import { ACCEPTED_IMAGE_TYPES } from "@/lib/datasets";

interface UploadDropzoneProps {
  busy: boolean;
  onFiles: (files: File[]) => void;
}

export function UploadDropzone({ busy, onFiles }: UploadDropzoneProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);

  function accept(list: FileList | null) {
    const files = Array.from(list ?? []);
    if (files.length > 0) onFiles(files);
  }

  return (
    <div
      onDragOver={(event) => {
        event.preventDefault();
        setDragging(true);
      }}
      onDragLeave={() => setDragging(false)}
      onDrop={(event) => {
        event.preventDefault();
        setDragging(false);
        if (!busy) accept(event.dataTransfer.files);
      }}
      className={`rounded-lg border border-dashed px-4 py-6 text-center transition-colors ${
        dragging ? "border-accent bg-accent/5" : "border-line"
      }`}
    >
      <ImagePlus aria-hidden className="text-muted mx-auto size-6" />
      <p className="mt-2 text-sm">
        {busy ? "Uploading…" : "Drop images here, or"}{" "}
        {!busy && (
          <label
            htmlFor="dataset-files"
            className="text-accent cursor-pointer underline-offset-2 hover:underline"
          >
            choose files
          </label>
        )}
      </p>
      <p className="text-faint mt-1 text-xs">
        PNG, JPEG or WebP. Invalid files and exact duplicates are skipped.
      </p>
      <input
        ref={inputRef}
        id="dataset-files"
        type="file"
        multiple
        accept={ACCEPTED_IMAGE_TYPES}
        aria-label="Upload images"
        disabled={busy}
        onChange={(event) => {
          accept(event.target.files);
          if (inputRef.current) inputRef.current.value = "";
        }}
        className="sr-only"
      />
    </div>
  );
}
