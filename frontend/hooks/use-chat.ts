"use client";

import { useMutation } from "@tanstack/react-query";

import { postChat } from "@/lib/api/chat";
import type { ChatRequest, ChatResponse } from "@/lib/api/types";

/** Mutation to ask a question against an indexed repo (blocking request). */
export function useChat() {
  return useMutation<ChatResponse, Error, ChatRequest>({
    mutationFn: (req) => postChat(req),
  });
}
