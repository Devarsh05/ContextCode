/**
 * Access-code storage + error helpers for the cost-control gate.
 *
 * The code is a UX friction-reducer only — the real enforcement is server-side.
 * It lives in sessionStorage (cleared when the tab closes) and is attached as
 * the `X-Access-Code` header on the two write endpoints.
 */

import { ApiError } from "@/lib/api/client";

export const ACCESS_CODE_STORAGE_KEY = "contextcode_access_code";

/** Read the stored access code, or null on the server / when unset. */
export function getStoredAccessCode(): string | null {
  if (typeof window === "undefined") return null;
  return window.sessionStorage.getItem(ACCESS_CODE_STORAGE_KEY);
}

/** Persist the access code for the current tab session. */
export function setStoredAccessCode(code: string): void {
  if (typeof window === "undefined") return;
  window.sessionStorage.setItem(ACCESS_CODE_STORAGE_KEY, code);
}

/** Forget the stored access code (e.g. after a 401). */
export function clearStoredAccessCode(): void {
  if (typeof window === "undefined") return;
  window.sessionStorage.removeItem(ACCESS_CODE_STORAGE_KEY);
}

/** True when the error is a 401 — the access code was missing or wrong. */
export function isUnauthorized(error: unknown): boolean {
  return error instanceof ApiError && error.status === 401;
}

/** True when the error is a 429 — the daily quota is spent (code was fine). */
export function isAtCapacity(error: unknown): boolean {
  return error instanceof ApiError && error.status === 429;
}

/** Shared copy for the "daily pool exhausted" case. */
export const AT_CAPACITY_MESSAGE =
  "Demo is at capacity for today. Please try again tomorrow.";
