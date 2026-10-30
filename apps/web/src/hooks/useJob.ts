"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { api, ApiError, errorMessage } from "@/lib/api";
import type { Job } from "@/lib/types";

const TERMINAL = new Set(["completed", "failed", "cancelled"]);
export const POLL_MS = 1000;
/** Give up after this many poll errors in a row (a 404 stops on the first one). */
export const MAX_POLL_FAILURES = 5;
export const JOB_LOST_CODE = "job_lost";
export const JOB_LOST_MESSAGE =
  "Job lost, API restarted. This run is no longer tracked. Start it again.";

export function isActive(job: Job | null): boolean {
  return job !== null && !TERMINAL.has(job.status);
}

/**
 * Starts a background job (generation or comparison) and follows its progress over Server-Sent
 * Events, falling back to polling if the stream drops (e.g. behind a proxy that buffers SSE).
 * Polling stops on 404 or after several failures so a restarted API does not spin forever.
 */
export function useJob(onFinished: (job: Job) => void) {
  const [job, setJob] = useState<Job | null>(null);
  const [startedAt, setStartedAt] = useState<number | null>(null);
  const [elapsedMs, setElapsedMs] = useState(0);
  const sourceRef = useRef<EventSource | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const onFinishedRef = useRef(onFinished);
  const jobRef = useRef<Job | null>(null);
  const watchingRef = useRef(false);
  const failuresRef = useRef(0);

  useEffect(() => {
    onFinishedRef.current = onFinished;
  }, [onFinished]);

  const stopWatching = useCallback(() => {
    watchingRef.current = false;
    sourceRef.current?.close();
    sourceRef.current = null;
    if (pollRef.current) clearInterval(pollRef.current);
    pollRef.current = null;
  }, []);

  const handleUpdate = useCallback(
    (update: Job) => {
      jobRef.current = update;
      setJob(update);
      if (TERMINAL.has(update.status)) {
        stopWatching();
        onFinishedRef.current(update);
      }
    },
    [stopWatching],
  );

  const giveUp = useCallback(() => {
    const current = jobRef.current;
    if (!watchingRef.current) return;
    if (!current || TERMINAL.has(current.status)) {
      stopWatching();
      return;
    }
    handleUpdate({
      ...current,
      status: "failed",
      message: JOB_LOST_MESSAGE,
      finished_at: Date.now() / 1000,
      error: { code: JOB_LOST_CODE, message: JOB_LOST_MESSAGE },
    });
  }, [handleUpdate, stopWatching]);

  const poll = useCallback(
    (jobId: string) => {
      if (pollRef.current) clearInterval(pollRef.current);
      failuresRef.current = 0;
      pollRef.current = setInterval(() => {
        api.getJob(jobId).then(
          (update) => {
            if (!watchingRef.current) return;
            failuresRef.current = 0;
            handleUpdate(update);
          },
          (error: unknown) => {
            if (!watchingRef.current) return;
            const missing = error instanceof ApiError && error.status === 404;
            failuresRef.current += 1;
            if (missing || failuresRef.current >= MAX_POLL_FAILURES) giveUp();
          },
        );
      }, POLL_MS);
    },
    [giveUp, handleUpdate],
  );

  const watch = useCallback(
    (jobId: string) => {
      watchingRef.current = true;
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
      jobRef.current = created;
      setJob(created);
      watch(created.id);
      return created;
    },
    [stopWatching, watch],
  );

  const cancel = useCallback(async (): Promise<string | null> => {
    if (!job || !isActive(job)) return null;
    try {
      const cancelled = await api.cancelGeneration(job.id);
      jobRef.current = cancelled;
      setJob(cancelled);
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
