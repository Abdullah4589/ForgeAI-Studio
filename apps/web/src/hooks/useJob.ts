"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { api, errorMessage } from "@/lib/api";
import type { Job } from "@/lib/types";

const TERMINAL = new Set(["completed", "failed", "cancelled"]);
const POLL_MS = 1000;

export function isActive(job: Job | null): boolean {
  return job !== null && !TERMINAL.has(job.status);
}

/**
 * Starts a background job (generation or comparison) and follows its progress over Server-Sent
 * Events, falling back to polling if the stream drops (e.g. behind a proxy that buffers SSE).
 */
export function useJob(onFinished: (job: Job) => void) {
  const [job, setJob] = useState<Job | null>(null);
  const [startedAt, setStartedAt] = useState<number | null>(null);
  const [elapsedMs, setElapsedMs] = useState(0);
  const sourceRef = useRef<EventSource | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const onFinishedRef = useRef(onFinished);

  useEffect(() => {
    onFinishedRef.current = onFinished;
  }, [onFinished]);

  const stopWatching = useCallback(() => {
    sourceRef.current?.close();
    sourceRef.current = null;
    if (pollRef.current) clearInterval(pollRef.current);
    pollRef.current = null;
  }, []);

  const handleUpdate = useCallback(
    (update: Job) => {
      setJob(update);
      if (TERMINAL.has(update.status)) {
        stopWatching();
        onFinishedRef.current(update);
      }
    },
    [stopWatching],
  );

  const poll = useCallback(
    (jobId: string) => {
      pollRef.current = setInterval(() => {
        api.getJob(jobId).then(handleUpdate, () => {
          // Keep polling; transient network errors shouldn't abandon a running job.
        });
      }, POLL_MS);
    },
    [handleUpdate],
  );

  const watch = useCallback(
    (jobId: string) => {
      const source = new EventSource(api.jobEventsUrl(jobId));
      sourceRef.current = source;
      source.onmessage = (event) => handleUpdate(JSON.parse(event.data) as Job);
      source.onerror = () => {
        if (sourceRef.current !== source) return;
        source.close();
        sourceRef.current = null;
        poll(jobId);
      };
    },
    [handleUpdate, poll],
  );

  const start = useCallback(
    async (create: () => Promise<Job>) => {
      stopWatching();
      const created = await create();
      // When reattaching to a job that is already running, count from its real start.
      setStartedAt(created.started_at ? created.started_at * 1000 : Date.now());
      setElapsedMs(0);
      setJob(created);
      watch(created.id);
      return created;
    },
    [stopWatching, watch],
  );

  const cancel = useCallback(async (): Promise<string | null> => {
    if (!job || !isActive(job)) return null;
    try {
      setJob(await api.cancelGeneration(job.id));
      return null;
    } catch (error) {
      return errorMessage(error);
    }
  }, [job]);

  const running = isActive(job);
  useEffect(() => {
    if (!running || startedAt === null) return;
    const timer = setInterval(() => setElapsedMs(Date.now() - startedAt), 200);
    return () => clearInterval(timer);
  }, [running, startedAt]);

  useEffect(() => stopWatching, [stopWatching]);

  return { job, elapsedMs, running, start, cancel };
}
