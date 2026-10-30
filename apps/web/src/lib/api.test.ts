import { afterEach, describe, expect, it, vi } from "vitest";
import { api, ApiError, errorMessage } from "./api";

function mockFetch(status: number, body: unknown) {
  const fetchMock = vi
    .fn()
    .mockResolvedValue(new Response(body === null ? null : JSON.stringify(body), { status }));
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

afterEach(() => {
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();
});

describe("api client", () => {
  it("builds history query strings without empty values", async () => {
    const fetchMock = mockFetch(200, { items: [], total: 0, page: 1, page_size: 20 });
    await api.listHistory({ q: "fox", model_id: 2, lora_id: undefined, sort: "oldest" });
    expect(fetchMock.mock.calls[0][0]).toBe(
      "http://localhost:8000/api/history?q=fox&model_id=2&sort=oldest",
    );
  });

  it("turns error envelopes into ApiError", async () => {
    mockFetch(422, {
      error: {
        code: "validation_error",
        message: "Some fields are invalid.",
        fields: [{ field: "width", message: "bad" }],
      },
    });
    const error = await api.getSystem().catch((e: unknown) => e);
    expect(error).toBeInstanceOf(ApiError);
    expect(error).toMatchObject({ status: 422, code: "validation_error" });
    expect((error as ApiError).fields).toEqual([{ field: "width", message: "bad" }]);
  });

  it("explains network failures", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("Failed to fetch")));
    const error = await api.getSystem().catch((e: unknown) => e);
    expect(errorMessage(error)).toMatch(/Cannot reach the ForgeAI API/);
  });

  it("handles 204 responses", async () => {
    mockFetch(204, null);
    await expect(api.deleteGeneration(1)).resolves.toBeUndefined();
  });

  it("sends a bearer token only when NEXT_PUBLIC_API_TOKEN is set", async () => {
    vi.stubEnv("NEXT_PUBLIC_API_TOKEN", "");
    const fetchMock = mockFetch(200, []);
    await api.listModels();
    expect(new Headers(fetchMock.mock.calls[0][1]?.headers).get("Authorization")).toBeNull();

    vi.stubEnv("NEXT_PUBLIC_API_TOKEN", "s3cret");
    await api.updateLora(1, { enabled: false });
    const headers = new Headers(fetchMock.mock.calls[1][1]?.headers);
    expect(headers.get("Authorization")).toBe("Bearer s3cret");
    expect(headers.get("Content-Type")).toBe("application/json");
  });
});
