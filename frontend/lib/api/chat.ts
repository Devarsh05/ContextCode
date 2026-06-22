import { apiFetch } from "@/lib/api/client";
import type { ChatRequest, ChatResponse } from "@/lib/api/types";
import { getStoredDemoSession } from "@/lib/demo-session";

/**
 * Ask a question against an indexed demo repo; returns a grounded answer +
 * citations. Public endpoint — admitted via the demo session minted from a
 * Turnstile challenge and sent as the `X-Demo-Session` header.
 */
export function postChat(req: ChatRequest): Promise<ChatResponse> {
  const session = getStoredDemoSession();
  return apiFetch<ChatResponse>("/chat", {
    method: "POST",
    body: JSON.stringify(req),
    headers: session ? { "X-Demo-Session": session } : {},
  });
}
