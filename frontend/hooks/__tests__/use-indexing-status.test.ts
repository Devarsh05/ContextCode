import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { useIndexingStatus } from "@/hooks/use-indexing-status";

/** Minimal EventSource stand-in that records instances and a close spy. */
class FakeEventSource {
  static instances: FakeEventSource[] = [];
  url: string;
  onmessage: ((ev: MessageEvent) => void) | null = null;
  onerror: ((ev: Event) => void) | null = null;
  close = vi.fn();

  constructor(url: string) {
    this.url = url;
    FakeEventSource.instances.push(this);
  }

  emit(data: string) {
    this.onmessage?.(new MessageEvent("message", { data }));
  }

  emitError() {
    this.onerror?.(new Event("error"));
  }
}

function latest() {
  const list = FakeEventSource.instances;
  return list[list.length - 1];
}

beforeEach(() => {
  FakeEventSource.instances = [];
  vi.stubGlobal("EventSource", FakeEventSource);
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("useIndexingStatus", () => {
  it("does not open a connection when repoId is null", () => {
    const { result } = renderHook(() => useIndexingStatus(null));
    expect(FakeEventSource.instances).toHaveLength(0);
    expect(result.current.done).toBe(false);
  });

  it("parses a progress frame into the exposed shape", () => {
    const { result } = renderHook(() => useIndexingStatus("repo-1"));

    act(() => {
      latest().emit(
        JSON.stringify({
          status: "running",
          progress_pct: 40,
          current_stage: "Parsing",
          error_message: null,
        }),
      );
    });

    expect(result.current).toEqual({
      status: "running",
      progressPct: 40,
      message: "Parsing",
      error: null,
      done: false,
    });
  });

  it("marks done and closes the connection on a completed frame", () => {
    const { result } = renderHook(() => useIndexingStatus("repo-1"));
    const source = latest();

    act(() => {
      source.emit(
        JSON.stringify({ status: "completed", progress_pct: 100 }),
      );
    });

    expect(result.current.status).toBe("completed");
    expect(result.current.done).toBe(true);
    expect(source.close).toHaveBeenCalledTimes(1);
  });

  it("surfaces a server error payload and closes", () => {
    const { result } = renderHook(() => useIndexingStatus("repo-1"));
    const source = latest();

    act(() => {
      source.emit(JSON.stringify({ error: "No indexing job found" }));
    });

    expect(result.current.error).toBe("No indexing job found");
    expect(result.current.done).toBe(true);
    expect(source.close).toHaveBeenCalledTimes(1);
  });

  it("closes the connection on a transport error", () => {
    const { result } = renderHook(() => useIndexingStatus("repo-1"));
    const source = latest();

    act(() => {
      source.emitError();
    });

    expect(result.current.done).toBe(true);
    expect(result.current.error).toMatch(/lost/i);
    expect(source.close).toHaveBeenCalledTimes(1);
  });

  it("closes the connection on unmount (cleanup)", () => {
    const { unmount } = renderHook(() => useIndexingStatus("repo-1"));
    const source = latest();

    unmount();

    expect(source.close).toHaveBeenCalledTimes(1);
  });
});
