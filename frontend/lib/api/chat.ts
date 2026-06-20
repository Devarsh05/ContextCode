import { getStoredAccessCode } from "@/lib/access-code";
import { apiFetch } from "@/lib/api/client";
import type { ChatRequest, ChatResponse } from "@/lib/api/types";

/** Ask a question against an indexed repo; returns a grounded answer + citations. */
export function postChat(req: ChatRequest): Promise<ChatResponse> {
  const code = getStoredAccessCode();
  return apiFetch<ChatResponse>("/chat", {
    method: "POST",
    body: JSON.stringify(req),
    headers: code ? { "X-Access-Code": code } : {},
  });
}
