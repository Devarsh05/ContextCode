/**
 * Demo-session storage + error helpers for the public chat gate.
 *
 * Chat is public but admitted only with a valid demo session: the user clears a
 * Cloudflare Turnstile challenge, we exchange the token for an opaque session id
 * (POST /demo/session), and attach it as the `X-Demo-Session` header on every
 * /chat request. The session lives in sessionStorage (cleared when the tab
 * closes) — mirroring the access-code gate. Real enforcement is server-side.
 */

import { ApiError } from "@/lib/api/client";

export const DEMO_SESSION_STORAGE_KEY = "contextcode_demo_session";

/** Read the stored demo session id, or null on the server / when unset. */
export function getStoredDemoSession(): string | null {
  if (typeof window === "undefined") return null;
  return window.sessionStorage.getItem(DEMO_SESSION_STORAGE_KEY);
}

/** Persist the demo session id for the current tab session. */
export function setStoredDemoSession(id: string): void {
  if (typeof window === "undefined") return;
  window.sessionStorage.setItem(DEMO_SESSION_STORAGE_KEY, id);
}

/** Forget the stored demo session (e.g. after a 401 expiry). */
export function clearStoredDemoSession(): void {
  if (typeof window === "undefined") return;
  window.sessionStorage.removeItem(DEMO_SESSION_STORAGE_KEY);
}

/** The human-readable `detail` string from an HTTPException-shaped error body. */
function errorDetail(error: unknown): string {
  if (!(error instanceof ApiError)) return "";
  const { detail } = error;
  if (typeof detail === "string") return detail;
  if (
    detail &&
    typeof detail === "object" &&
    "detail" in detail &&
    typeof (detail as { detail: unknown }).detail === "string"
  ) {
    return (detail as { detail: string }).detail;
  }
  return "";
}

/** True when the demo session is missing or expired (401) — re-mint and retry. */
export function isExpiredSession(error: unknown): boolean {
  return error instanceof ApiError && error.status === 401;
}

/** True for the 429 raised when this session has spent its per-session cap. */
export function isAtSessionLimit(error: unknown): boolean {
  return (
    error instanceof ApiError &&
    error.status === 429 &&
    /session/i.test(errorDetail(error))
  );
}

/** True for the 429 raised when the global daily pool is exhausted. */
export function isAtGlobalLimit(error: unknown): boolean {
  return (
    error instanceof ApiError && error.status === 429 && !isAtSessionLimit(error)
  );
}

/** Copy for the per-session cap (this tab is done for now). */
export const SESSION_LIMIT_MESSAGE =
  "You've hit the demo limit for this session.";

/** Copy for the global daily pool being spent (everyone is throttled). */
export const GLOBAL_LIMIT_MESSAGE =
  "The demo is busy today — please try again later.";
