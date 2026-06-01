import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiError, apiFetch } from "@/lib/api/client";

function mockFetch(response: Response) {
  const fn = vi.fn().mockResolvedValue(response);
  vi.stubGlobal("fetch", fn);
  return fn;
}

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("apiFetch", () => {
  it("returns parsed JSON on a 2xx response", async () => {
    const body = { repo_id: "abc", job_id: "job-1", status: "queued" };
    mockFetch(
      new Response(JSON.stringify(body), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );

    const result = await apiFetch<typeof body>("/repos/index", {
      method: "POST",
    });

    expect(result).toEqual(body);
  });

  it("throws a typed ApiError with parsed detail on a non-2xx response", async () => {
    const detail = { detail: [{ loc: ["body", "question"], msg: "required" }] };
    mockFetch(
      new Response(JSON.stringify(detail), {
        status: 422,
        statusText: "Unprocessable Entity",
        headers: { "Content-Type": "application/json" },
      }),
    );

    const error = await apiFetch("/chat", { method: "POST" }).catch(
      (e: unknown) => e,
    );

    expect(error).toBeInstanceOf(ApiError);
    const apiError = error as ApiError;
    expect(apiError.status).toBe(422);
    expect(apiError.statusText).toBe("Unprocessable Entity");
    expect(apiError.detail).toEqual(detail);
  });

  it("falls back to raw text when the error body is not JSON", async () => {
    mockFetch(
      new Response("upstream exploded", {
        status: 500,
        statusText: "Internal Server Error",
      }),
    );

    const error = (await apiFetch("/health").catch((e: unknown) => e)) as ApiError;

    expect(error).toBeInstanceOf(ApiError);
    expect(error.status).toBe(500);
    expect(error.detail).toBe("upstream exploded");
  });
});
