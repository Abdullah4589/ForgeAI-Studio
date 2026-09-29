import { ShieldAlert } from "lucide-react";

/**
 * Shown instead of an image the model's safety checker replaced with a black frame, so users
 * understand why instead of seeing an unexplained black square.
 */
export function BlockedImage({ compact = false }: { compact?: boolean }) {
  return (
    <div
      role="img"
      aria-label="Blocked by the safety checker"
      className="bg-raised text-muted flex aspect-square w-full flex-col items-center justify-center gap-2 p-4 text-center"
    >
      <ShieldAlert aria-hidden className={compact ? "size-5" : "size-7"} />
      {!compact && (
        <>
          <p className="text-ink text-sm font-medium">Blocked by the safety checker</p>
          <p className="max-w-[32ch] text-xs leading-relaxed">
            The model flagged this image and returned a black frame instead. This can be a false
            positive, especially with few steps. Try more steps or a different seed.
          </p>
        </>
      )}
    </div>
  );
}
