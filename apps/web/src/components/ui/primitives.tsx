import type { ButtonHTMLAttributes, ReactNode } from "react";
import { AlertTriangle } from "lucide-react";

type ButtonVariant = "primary" | "secondary" | "ghost" | "danger";

const BUTTON_STYLES: Record<ButtonVariant, string> = {
  primary:
    "bg-accent text-accent-ink hover:bg-accent-strong disabled:bg-raised disabled:text-faint",
  secondary: "border border-line bg-raised text-ink hover:border-faint disabled:text-faint",
  ghost: "text-muted hover:bg-raised hover:text-ink disabled:text-faint",
  danger: "border border-danger/40 text-danger hover:bg-danger/10 disabled:opacity-50",
};

export function Button({
  variant = "secondary",
  className = "",
  type = "button",
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: ButtonVariant }) {
  return (
    <button
      type={type}
      className={`inline-flex items-center justify-center gap-2 rounded-md px-3 py-2 text-sm font-medium whitespace-nowrap transition-colors active:translate-y-px disabled:cursor-not-allowed ${BUTTON_STYLES[variant]} ${className}`}
      {...props}
    />
  );
}

export function IconButton({
  label,
  children,
  className = "",
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { label: string }) {
  return (
    <button
      type="button"
      aria-label={label}
      title={label}
      className={`text-muted hover:bg-raised hover:text-ink inline-flex size-8 items-center justify-center rounded-md transition-colors ${className}`}
      {...props}
    >
      {children}
    </button>
  );
}

export function Panel({
  title,
  actions,
  children,
  className = "",
}: {
  title?: string;
  actions?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section className={`border-line bg-panel rounded-lg border p-4 ${className}`}>
      {(title || actions) && (
        <div className="mb-3 flex items-center justify-between gap-2">
          {title && <h2 className="text-ink text-sm font-semibold">{title}</h2>}
          {actions}
        </div>
      )}
      {children}
    </section>
  );
}

export function PageHeader({
  title,
  description,
  actions,
}: {
  title: string;
  description?: string;
  actions?: ReactNode;
}) {
  return (
    <header className="mb-6 flex flex-wrap items-end justify-between gap-4">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">{title}</h1>
        {description && <p className="text-muted mt-1 max-w-[65ch] text-sm">{description}</p>}
      </div>
      {actions && <div className="flex gap-2">{actions}</div>}
    </header>
  );
}

export function ErrorBanner({ message }: { message: string | null }) {
  if (!message) return null;
  return (
    <div
      role="alert"
      className="border-danger/40 bg-danger/10 text-danger flex items-start gap-2 rounded-md border px-3 py-2 text-sm"
    >
      <AlertTriangle aria-hidden className="mt-0.5 size-4 shrink-0" />
      <span>{message}</span>
    </div>
  );
}

export function EmptyState({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <div className="border-line rounded-lg border border-dashed px-6 py-12 text-center">
      <p className="text-ink font-medium">{title}</p>
      {children && <div className="text-muted mt-2 text-sm">{children}</div>}
    </div>
  );
}

export function Badge({
  tone = "neutral",
  children,
}: {
  tone?: "neutral" | "ok" | "warn" | "accent";
  children: ReactNode;
}) {
  const tones = {
    neutral: "border-line text-muted",
    ok: "border-ok/40 text-ok",
    warn: "border-danger/40 text-danger",
    accent: "border-accent/50 text-accent",
  };
  return (
    <span
      className={`inline-flex items-center rounded border px-1.5 py-0.5 text-xs ${tones[tone]}`}
    >
      {children}
    </span>
  );
}

export const inputClass =
  "w-full rounded-md border border-line bg-canvas px-3 py-2 text-sm text-ink placeholder:text-faint focus:border-accent focus:outline-none aria-[invalid=true]:border-danger";

export function FieldError({ id, message }: { id: string; message?: string }) {
  if (!message) return null;
  return (
    <p id={id} className="text-danger mt-1 text-xs">
      {message}
    </p>
  );
}
