"use client";

import { useCallback, useEffect, useState } from "react";

import {
  clearStoredAccessCode,
  getStoredAccessCode,
  setStoredAccessCode,
} from "@/lib/access-code";

export interface UseAccessCode {
  /** The stored access code, or null until set / after clear. */
  code: string | null;
  /** Persist a new code for this tab session. */
  setCode: (code: string) => void;
  /** Forget the stored code (e.g. after a 401). */
  clearCode: () => void;
}

/**
 * sessionStorage-backed access code. Hydrated in an effect (not during render)
 * to avoid an SSR/client markup mismatch.
 */
export function useAccessCode(): UseAccessCode {
  const [code, setCodeState] = useState<string | null>(null);

  useEffect(() => {
    setCodeState(getStoredAccessCode());
  }, []);

  const setCode = useCallback((value: string) => {
    setStoredAccessCode(value);
    setCodeState(value);
  }, []);

  const clearCode = useCallback(() => {
    clearStoredAccessCode();
    setCodeState(null);
  }, []);

  return { code, setCode, clearCode };
}
