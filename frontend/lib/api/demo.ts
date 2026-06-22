import { apiFetch } from "@/lib/api/client";
import type { DemoRepoResponse, DemoSessionResponse } from "@/lib/api/types";

/** List the curated demo repositories (read-only, ungated). */
export function listDemoRepos(): Promise<DemoRepoResponse[]> {
  return apiFetch<DemoRepoResponse[]>("/repos/demos");
}

/**
 * Exchange a Cloudflare Turnstile token for an opaque demo session id, used as
 * the `X-Demo-Session` header on public chat calls. 403 on a failed challenge.
 */
export function postDemoSession(token: string): Promise<DemoSessionResponse> {
  return apiFetch<DemoSessionResponse>("/demo/session", {
    method: "POST",
    body: JSON.stringify({ token }),
  });
}
