"use client";

import { useEffect, useRef, useState } from "react";
import { MessagesSquare } from "lucide-react";

import { useChat } from "@/hooks/use-chat";
import { useAccessCode } from "@/hooks/use-access-code";
import {
  AT_CAPACITY_MESSAGE,
  getStoredAccessCode,
  isAtCapacity,
  isUnauthorized,
} from "@/lib/access-code";
import { AccessCodeModal } from "@/components/access-code-modal";
import { ChatComposer } from "@/components/repo/chat/chat-composer";
import { ChatMessageItem } from "@/components/repo/chat/chat-message";
import { ChatThinking } from "@/components/repo/chat/chat-thinking";
import type { ChatMessage } from "@/components/repo/chat/types";

const SUGGESTIONS = [
  "What does this project do?",
  "How is the codebase structured?",
  "Where does request handling start?",
];

/**
 * Chat tab for an indexed repo. Messages live in local state only — there is no
 * persistence (multi-user/auth is out of scope). Each ask is a blocking POST
 * /chat via useChat; while pending we show an animated thinking bubble.
 */
export function ChatPanel({ repoId }: { repoId: string }) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const chat = useChat();
  const { setCode, clearCode } = useAccessCode();
  const idRef = useRef(0);
  const bottomRef = useRef<HTMLDivElement>(null);
  const [modalOpen, setModalOpen] = useState(false);
  const [modalError, setModalError] = useState<string | null>(null);
  const pendingAskRef = useRef<{ question: string; withUserBubble: boolean } | null>(
    null,
  );

  useEffect(() => {
    bottomRef.current?.scrollIntoView?.({ behavior: "smooth" });
  }, [messages.length, chat.isPending]);

  function nextId() {
    return String((idRef.current += 1));
  }

  /**
   * Send a question to the model. `withUserBubble` is false when retrying a
   * failed turn — the user prompt is already in the thread, so we only append
   * the new assistant reply.
   */
  function ask(question: string, { withUserBubble = true } = {}) {
    // Gate: prompt for the access code before sending if none is stored yet.
    // The user bubble is deferred until a code exists so a cancelled prompt
    // leaves no orphaned message.
    if (!getStoredAccessCode()) {
      pendingAskRef.current = { question, withUserBubble };
      setModalError(null);
      setModalOpen(true);
      return;
    }

    if (withUserBubble) {
      setMessages((prev) => [
        ...prev,
        { id: nextId(), role: "user", content: question },
      ]);
    }

    chat.mutate(
      { repo_id: repoId, question },
      {
        onSuccess: (data) =>
          setMessages((prev) => [
            ...prev,
            {
              id: nextId(),
              role: "assistant",
              answer: data.answer,
              citations: data.citations,
            },
          ]),
        onError: (error) => {
          // Wrong/stale code: clear it and reprompt (the user bubble already
          // exists, so the resubmit must not add another).
          if (isUnauthorized(error)) {
            clearCode();
            pendingAskRef.current = { question, withUserBubble: false };
            setModalError("Invalid access code. Please try again.");
            setModalOpen(true);
            return;
          }
          // Daily pool spent: surface the capacity message, no reprompt.
          const answer = isAtCapacity(error)
            ? AT_CAPACITY_MESSAGE
            : error.message || "The request failed. Please try again.";
          setMessages((prev) => [
            ...prev,
            {
              id: nextId(),
              role: "assistant",
              answer,
              citations: [],
              isError: true,
              question,
            },
          ]);
        },
      },
    );
  }

  function handleSubmit(question: string) {
    ask(question);
  }

  /** Drop the failed error turn and re-ask its question (no new user bubble). */
  function handleRetry(errorId: string, question: string) {
    setMessages((prev) => prev.filter((message) => message.id !== errorId));
    ask(question, { withUserBubble: false });
  }

  const isEmpty = messages.length === 0 && !chat.isPending;

  return (
    <>
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
            {chat.isPending && <ChatThinking />}
            <div ref={bottomRef} />
          </div>
        )}
      </div>

      <ChatComposer onSubmit={handleSubmit} pending={chat.isPending} />
    </div>

    <AccessCodeModal
      open={modalOpen}
      error={modalError}
      onClose={() => setModalOpen(false)}
      onSubmit={(submitted) => {
        setCode(submitted);
        setModalOpen(false);
        const pending = pendingAskRef.current;
        pendingAskRef.current = null;
        if (pending) ask(pending.question, { withUserBubble: pending.withUserBubble });
      }}
    />
    </>
  );
}
