import type { CitationResponse } from "@/lib/api/types";

export interface UserMessage {
  id: string;
  role: "user";
  content: string;
}

export interface AssistantMessage {
  id: string;
  role: "assistant";
  answer: string;
  citations: CitationResponse[];
  /** True when the answer is a client-side error notice, not a model reply. */
  isError?: boolean;
  /** The question that produced this error, so the turn can be retried. */
  question?: string;
}

export type ChatMessage = UserMessage | AssistantMessage;
