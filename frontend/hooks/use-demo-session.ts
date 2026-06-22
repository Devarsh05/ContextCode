"use client";

import { useCallback, useEffect, useState } from "react";

import { postDemoSession } from "@/lib/api/demo";
import {
  clearStoredDemoSession,
  getStoredDemoSession,
  setStoredDemoSession,
} from "@/lib/demo-session";
import { executeTurnstile } from "@/lib/turnstile";

export interface UseDemoSession {
  /** The stored session id, or null until minted / after clear. */
  sessionId: string | null;
  /** Return the stored session, minting one (Turnstile → /demo/session) if absent. */
  ensureSession: () => Promise<string>;
  /** Force a fresh mint, discarding any stored session (e.g. after a 401). */
  refreshSession: () => Promise<string>;
  /** Forget the stored session. */
  clearSession: () => void;
}

/**
 * sessionStorage-backed demo session, mirroring {@link useAccessCode}. Minting
 * runs a Cloudflare Turnstile challenge and exchanges the token for a session id
 * via POST /demo/session. Hydrated in an effect (not during render) to avoid an
 * SSR/client markup mismatch.
 */
export function useDemoSession(): UseDemoSession {
  const [sessionId, setSessionId] = useState<string | null>(null);

  useEffect(() => {
    setSessionId(getStoredDemoSession());
  }, []);

  const mint = useCallback(async (): Promise<string> => {
    const siteKey = process.env.NEXT_PUBLIC_TURNSTILE_SITE_KEY;
    if (!siteKey) {
      throw new Error(
        "Turnstile is not configured (set NEXT_PUBLIC_TURNSTILE_SITE_KEY).",
      );
    }
    const token = await executeTurnstile(siteKey);
    const { session_id } = await postDemoSession(token);
    setStoredDemoSession(session_id);
    setSessionId(session_id);
    return session_id;
  }, []);

  const ensureSession = useCallback(async (): Promise<string> => {
    return getStoredDemoSession() ?? (await mint());
  }, [mint]);

  const refreshSession = useCallback(async (): Promise<string> => {
    clearStoredDemoSession();
    setSessionId(null);
    return mint();
  }, [mint]);

  const clearSession = useCallback(() => {
    clearStoredDemoSession();
    setSessionId(null);
  }, []);

  return { sessionId, ensureSession, refreshSession, clearSession };
}
