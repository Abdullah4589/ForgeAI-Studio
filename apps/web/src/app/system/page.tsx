"use client";

import { useEffect, useState } from "react";
import { ErrorBanner, PageHeader, Panel } from "@/components/ui/primitives";
import { api, errorMessage } from "@/lib/api";
import { formatBytes } from "@/lib/format";
import type { SystemInfo } from "@/lib/types";

const REFRESH_MS = 5000;

export default function SystemPage() {
  const [info, setInfo] = useState<SystemInfo | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    const load = () =>
      api.getSystem().then(
        (result) => {
          if (!active) return;
          setInfo(result);
          setError(null);
        },
        (err: unknown) => {
          if (active) setError(errorMessage(err));
        },
      );
    void load();
    const timer = setInterval(load, REFRESH_MS);
    return () => {
      active = false;
      clearInterval(timer);
    };
  }, []);

  return (
    <div className="mx-auto max-w-[1100px]">
      <PageHeader
        title="System"
        description={`Hardware and runtime status, refreshed every ${REFRESH_MS / 1000} seconds.`}
      />
      <ErrorBanner message={error} />
      {info && (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
          <Panel title="GPU">
            {!info.cuda_available && (
              <p className="text-muted mb-3 text-sm">
                No CUDA GPU detected. ForgeAI Studio runs in CPU mode, which works but is much
                slower.
              </p>
            )}
            <Stats
              rows={[
                ["GPU", info.gpu_name ?? "None"],
                ["CUDA available", info.cuda_available ? "Yes" : "No"],
                ["CUDA version", info.cuda_version ?? "n/a"],
                ["VRAM total", formatBytes(info.vram_total_bytes)],
                ["VRAM used", formatBytes(info.vram_used_bytes)],
                ["VRAM available", formatBytes(info.vram_free_bytes)],
              ]}
            />
            {info.vram_total_bytes && info.vram_used_bytes !== null && (
              <Meter label="VRAM usage" used={info.vram_used_bytes} total={info.vram_total_bytes} />
            )}
          </Panel>
          <Panel title="Runtime">
            <Stats
              rows={[
                ["Compute device", info.device.toUpperCase()],
                ["Generation backend", info.generation_backend],
                [
                  "PyTorch",
                  info.torch_installed ? (info.torch_version ?? "installed") : "Not installed",
                ],
              ]}
            />
          </Panel>
          <Panel title="CPU and memory">
            <Stats
              rows={[
                ["CPU usage", `${info.cpu_percent.toFixed(1)}%`],
                ["CPU cores", String(info.cpu_count ?? "n/a")],
                ["RAM total", formatBytes(info.ram_total_bytes)],
                ["RAM used", formatBytes(info.ram_used_bytes)],
                ["RAM available", formatBytes(info.ram_available_bytes)],
              ]}
            />
            <Meter label="RAM usage" used={info.ram_used_bytes} total={info.ram_total_bytes} />
          </Panel>
          <Panel title="Disk (output directory)">
            <Stats
              rows={[
                ["Total", formatBytes(info.disk_total_bytes)],
                ["Used", formatBytes(info.disk_used_bytes)],
                ["Free", formatBytes(info.disk_free_bytes)],
              ]}
            />
            <Meter label="Disk usage" used={info.disk_used_bytes} total={info.disk_total_bytes} />
          </Panel>
        </div>
      )}
    </div>
  );
}

function Stats({ rows }: { rows: [string, string][] }) {
  return (
    <dl className="grid grid-cols-[max-content_1fr] gap-x-4 gap-y-1.5 text-sm">
      {rows.map(([label, value]) => (
        <div key={label} className="contents">
          <dt className="text-muted">{label}</dt>
          <dd className="font-mono tabular-nums">{value}</dd>
        </div>
      ))}
    </dl>
  );
}

function Meter({ label, used, total }: { label: string; used: number; total: number }) {
  const percent = total > 0 ? Math.round((used / total) * 100) : 0;
  return (
    <div
      role="meter"
      aria-label={label}
      aria-valuemin={0}
      aria-valuemax={100}
      aria-valuenow={percent}
      className="bg-raised mt-3 h-1.5 overflow-hidden rounded-full"
    >
      <div className="bg-accent h-full" style={{ width: `${percent}%` }} />
    </div>
  );
}
