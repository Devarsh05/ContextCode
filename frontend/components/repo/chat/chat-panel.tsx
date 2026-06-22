"use client";

import { useEffect, useRef, useState } from "react";
import { MessagesSquare } from "lucide-react";

import { useChat } from "@/hooks/use-chat";
import { useDemoSession } from "@/hooks/use-demo-session";
import {
  GLOBAL_LIMIT_MESSAGE,
  SESSION_LIMIT_MESSAGE,
  isAtGlobalLimit,
  isAtSessionLimit,
  isExpiredSession,
} from "@/lib/demo-session";
import { ChatComposer } from "@/components/repo/chat/chat-composer";
import { ChatMessageItem } from "@/components/repo/chat/chat-message";
import { ChatThinking } from "@/components/repo/chat/chat-thinking";
import type { ChatMessage } from "@/components/repo/chat/types";
import type { CitationResponse } from "@/lib/api/types";

const SUGGESTIONS = [
  "What does this project do?",
  "How is the codebase structured?",
  "Where does request handling start?",
];

const VERIFY_FAILED_MESSAGE =
  "We couldn't verify you're human. Please try again.";

/**
 * Chat tab for an indexed demo repo. Messages live in local state only — there
 * is no persistence (multi-user/auth is out of scope). Chat is public but gated
 * by a demo session: the first ask mints one via a Turnstile challenge, then
 * each ask is a blocking POST /chat carrying the `X-Demo-Session` header. While
 * verifying or awaiting the model we show an animated thinking bubble.
 */
export function ChatPanel({ repoId }: { repoId: string }) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const chat = useChat();
  const { ensureSession, refreshSession, clearSession } = useDemoSession();
  // True while minting a demo session (running Turnstile) before the request.
  const [verifying, setVerifying] = useState(false);
  const idRef = useRef(0);
  const bottomRef = useRef<HTMLDivElement>(null);

  const busy = chat.isPending || verifying;

  useEffect(() => {
    bottomRef.current?.scrollIntoView?.({ behavior: "smooth" });
  }, [messages.length, busy]);

  function nextId() {
    return String((idRef.current += 1));
  }

  function appendAssistant(
    answer: string,
    extra: {
      citations?: CitationResponse[];
      isError?: boolean;
      question?: string;
    } = {},
  ) {
    setMessages((prev) => [
      ...prev,
      {
        id: nextId(),
        role: "assistant",
        answer,
        citations: extra.citations ?? [],
        isError: extra.isError,
        question: extra.question,
      },
    ]);
  }

  /** Fire the POST /chat mutation. `canRemint` allows one silent re-mint on 401. */
  function send(question: string, { canRemint }: { canRemint: boolean }) {
    chat.mutate(
      { repo_id: repoId, question },
      {
        onSuccess: (data) =>
          appendAssistant(data.answer, { citations: data.citations }),
        onError: async (error) => {
          // Expired/invalid session: silently re-mint and retry exactly once.
          if (isExpiredSession(error) && canRemint) {
            try {
              clearSession();
              await refreshSession();
              send(question, { canRemint: false });
              return;
            } catch {
              appendAssistant(VERIFY_FAILED_MESSAGE, {
                isError: true,
                question,
              });
              return;
            }
          }

          const answer = isAtSessionLimit(error)
            ? SESSION_LIMIT_MESSAGE
            : isAtGlobalLimit(error)
              ? GLOBAL_LIMIT_MESSAGE
              : error.message || "The request failed. Please try again.";
          appendAssistant(answer, { isError: true, question });
        },
      },
    );
  }

  /**
   * Send a question to the model. `withUserBubble` is false when retrying a
   * failed turn — the user prompt is already in the thread, so we only append
   * the new assistant reply.
   */
  async function ask(question: string, { withUserBubble = true } = {}) {
    if (withUserBubble) {
      setMessages((prev) => [
        ...prev,
        { id: nextId(), role: "user", content: question },
      ]);
    }

    // Ensure a demo session before spending an LLM call. Minting runs Turnstile.
    setVerifying(true);
    try {
      await ensureSession();
    } catch {
      appendAssistant(VERIFY_FAILED_MESSAGE, { isError: true, question });
      return;
    } finally {
      setVerifying(false);
    }

    send(question, { canRemint: true });
  }

  function handleSubmit(question: string) {
    void ask(question);
  }

  /** Drop the failed error turn and re-ask its question (no new user bubble). */
  function handleRetry(errorId: string, question: string) {
    setMessages((prev) => prev.filter((message) => message.id !== errorId));
    void ask(question, { withUserBubble: false });
  }

  const isEmpty = messages.length === 0 && !busy;

  return (
    <div className="flex h-[calc(100vh-15rem)] min-h-[420px] flex-col gap-4">
      <div className="flex-1 overflow-y-auto">
        {isEmpty ? (
          <div className="flex h-full flex-col items-center justify-center gap-4 px-6 text-center">
            <MessagesSquare className="size-8 text-muted-foreground" />
            <div>
              <p className="text-sm font-medium">Ask anything about this repo</p>
              <p className="mt-1 text-sm text-muted-foreground">
                Answers are grounded in the indexed code, with citations.
              </p>
            </div>
            <div className="flex flex-wrap justify-center gap-2">
              {SUGGESTIONS.map((suggestion) => (
                <button
                  key={suggestion}
                  type="button"
                  onClick={() => handleSubmit(suggestion)}
                  className="rounded-full border border-border bg-card px-3 py-1.5 text-xs text-muted-foreground transition-colors hover:bg-accent hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background"
                >
                  {suggestion}
                </button>
              ))}
            </div>
          </div>
        ) : (
          <div className="space-y-4 py-1">
            {messages.map((message) => (
              <ChatMessageItem
                key={message.id}
                message={message}
                onRetry={
                  message.role === "assistant" &&
                  message.isError &&
                  message.question
                    ? () => handleRetry(message.id, message.question!)
                    : undefined
                }
              />
            ))}
            {busy && <ChatThinking />}
            <div ref={bottomRef} />
          </div>
        )}
      </div>

      <ChatComposer onSubmit={handleSubmit} pending={busy} />
    </div>
  );
}
