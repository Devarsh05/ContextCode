"use client";

import { useEffect, useRef, useState } from "react";

import { API_BASE_URL } from "@/lib/api/client";

/**
 * Shape of a single SSE frame from GET /repos/{id}/status. The status stream is
 * typed as `unknown` in the generated OpenAPI types (it is not a JSON response
 * body), so this is the one place a stream shape is declared by hand. It mirrors
 * the backend payload in app/api/repos.py.
 */
interface IndexingStatusEvent {
  status?: string;
  progress_pct?: number;
  current_stage?: string | null;
  error_message?: string | null;
  error?: string;
}

export interface IndexingStatus {
  status: string | null;
  progressPct: number | null;
  message: string | null;
  error: string | null;
  done: boolean;
}

const INITIAL: IndexingStatus = {
  status: null,
  progressPct: null,
  message: null,
  error: null,
  done: false,
};

const TERMINAL_STATUSES = new Set(["completed", "failed"]);

/**
 * Subscribe to a repo's indexing progress over the browser EventSource API.
 * Closes the connection on a terminal status, on error, and on unmount.
 */
export function useIndexingStatus(repoId: string | null): IndexingStatus {
  const [state, setState] = useState<IndexingStatus>(INITIAL);
  const sourceRef = useRef<EventSource | null>(null);

  useEffect(() => {
    if (!repoId) {
      setState(INITIAL);
      return;
    }

    setState(INITIAL);

    const source = new EventSource(
      `${API_BASE_URL}/repos/${repoId}/status`,
    );
    sourceRef.current = source;

    const close = () => {
      source.close();
      sourceRef.current = null;
    };

    source.onmessage = (event: MessageEvent<string>) => {
      let payload: IndexingStatusEvent;
      try {
        payload = JSON.parse(event.data);
      } catch {
        return;
      }

      if (payload.error) {
        setState({
          status: null,
          progressPct: null,
          message: null,
          error: payload.error,
          done: true,
        });
        close();
        return;
      }

      const done = payload.status
        ? TERMINAL_STATUSES.has(payload.status)
        : false;

      setState({
        status: payload.status ?? null,
        progressPct: payload.progress_pct ?? null,
        message: payload.current_stage ?? null,
        error: payload.error_message ?? null,
        done,
      });

      if (done) {
        close();
      }
    };

    source.onerror = () => {
      setState((prev) =>
        prev.done
          ? prev
          : { ...prev, error: "Connection to status stream lost", done: true },
      );
      close();
    };

    return () => {
      sourceRef.current?.close();
      sourceRef.current = null;
    };
  }, [repoId]);

  return state;
}
