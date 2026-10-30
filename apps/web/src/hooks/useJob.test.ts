import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError } from "@/lib/api";
import type { Job } from "@/lib/types";
import { JOB_LOST_CODE, JOB_LOST_MESSAGE, MAX_POLL_FAILURES, POLL_MS, useJob } from "./useJob";

const getJob = vi.hoisted(() => vi.fn());

vi.mock("@/lib/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/api")>();
  return {
    ...actual,
    api: {
      ...actual.api,
      getJob,
      jobEventsUrl: (id: string) => `http://localhost:8000/api/jobs/${id}/events`,
    },
  };
});

class FakeEventSource {
  static latest: FakeEventSource | null = null;
  onmessage: ((event: MessageEvent) => void) | null = null;
  onerror: ((event: Event) => void) | null = null;
  constructor(public url: string) {
    FakeEventSource.latest = this;
  }
  close() {}
}

const runningJob: Job = {
  id: "job-1",
  kind: "generation",
  status: "running",
  step: 1,
  total_steps: 4,
  message: "Step 1 of 4",
  created_at: 0,
  started_at: 1,
  finished_at: null,
  result: null,
  error: null,
};

async function startWatching() {
  const onFinished = vi.fn();
  const hook = renderHook(() => useJob(onFinished));
  await act(async () => {
    await hook.result.current.start(async () => runningJob);
  });
  return { ...hook, onFinished };
}

function dropStream() {
  act(() => {
    FakeEventSource.latest?.onerror?.(new Event("error"));
  });
}

beforeEach(() => {
  FakeEventSource.latest = null;
  getJob.mockReset();
  vi.stubGlobal("EventSource", FakeEventSource);
  vi.useFakeTimers();
});

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

describe("useJob polling", () => {
  it("stops on 404 and reports that the API restarted", async () => {
    getJob.mockRejectedValue(new ApiError("Job not found.", 404, "not_found"));
    const { result, onFinished } = await startWatching();
    dropStream();

    await act(async () => {
      await vi.advanceTimersByTimeAsync(POLL_MS);
    });

    expect(getJob).toHaveBeenCalledTimes(1);
    expect(result.current.running).toBe(false);
    expect(result.current.job).toMatchObject({
      status: "failed",
      error: { code: JOB_LOST_CODE, message: JOB_LOST_MESSAGE },
    });
    expect(onFinished).toHaveBeenCalledWith(result.current.job);
    expect(JOB_LOST_MESSAGE).toMatch(/Job lost, API restarted/);

    await act(async () => {
      await vi.advanceTimersByTimeAsync(POLL_MS * 5);
    });
    expect(getJob).toHaveBeenCalledTimes(1);
  });

  it("stops after consecutive failures and keeps polling when one succeeds", async () => {
    getJob.mockRejectedValue(new ApiError("Cannot reach the API.", 0, "network_error"));
    const lost = await startWatching();
    dropStream();
    await act(async () => {
      await vi.advanceTimersByTimeAsync(POLL_MS * MAX_POLL_FAILURES);
    });
    expect(getJob).toHaveBeenCalledTimes(MAX_POLL_FAILURES);
    expect(lost.result.current.job?.error?.code).toBe(JOB_LOST_CODE);
    expect(lost.result.current.running).toBe(false);

    getJob.mockReset();
    getJob
      .mockRejectedValueOnce(new ApiError("Cannot reach the API.", 0, "network_error"))
      .mockResolvedValueOnce({ ...runningJob, step: 2 });
    const recovered = await startWatching();
    dropStream();
    await act(async () => {
      await vi.advanceTimersByTimeAsync(POLL_MS * 2);
    });
    expect(recovered.result.current.running).toBe(true);
    expect(recovered.result.current.job?.step).toBe(2);

    getJob.mockRejectedValue(new ApiError("Cannot reach the API.", 0, "network_error"));
    await act(async () => {
      await vi.advanceTimersByTimeAsync(POLL_MS * (MAX_POLL_FAILURES - 1));
    });
    expect(recovered.result.current.running).toBe(true);
    await act(async () => {
      await vi.advanceTimersByTimeAsync(POLL_MS);
    });
    expect(recovered.result.current.job?.error?.code).toBe(JOB_LOST_CODE);
  });
});
