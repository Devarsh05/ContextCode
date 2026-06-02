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
}

export type ChatMessage = UserMessage | AssistantMessage;
