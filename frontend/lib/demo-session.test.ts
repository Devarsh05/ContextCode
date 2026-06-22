import { describe, expect, it } from "vitest";

import { ApiError } from "@/lib/api/client";
import {
  isAtGlobalLimit,
  isAtSessionLimit,
  isExpiredSession,
} from "@/lib/demo-session";

function apiError(status: number, detail: string): ApiError {
  return new ApiError(status, "", { detail });
}

describe("demo-session error classification", () => {
  it("treats a 401 as an expired session", () => {
    expect(isExpiredSession(apiError(401, "Missing or invalid demo session"))).toBe(
      true,
    );
    expect(isExpiredSession(apiError(429, "anything"))).toBe(false);
    expect(isExpiredSession(new Error("boom"))).toBe(false);
  });

  it("classifies a 429 mentioning the session as the per-session cap", () => {
    const err = apiError(
      429,
      "You've reached the demo message limit for this session.",
    );
    expect(isAtSessionLimit(err)).toBe(true);
    expect(isAtGlobalLimit(err)).toBe(false);
  });

  it("classifies a generic 429 as the global cap", () => {
    const err = apiError(
      429,
      "Demo is at capacity for today. Please try again tomorrow.",
    );
    expect(isAtGlobalLimit(err)).toBe(true);
    expect(isAtSessionLimit(err)).toBe(false);
  });

  it("ignores non-429 / non-ApiError values for the cap checks", () => {
    expect(isAtSessionLimit(apiError(401, "for this session"))).toBe(false);
    expect(isAtGlobalLimit(new Error("network"))).toBe(false);
  });
});
