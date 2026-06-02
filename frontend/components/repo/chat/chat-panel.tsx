"use client";

import { useEffect, useRef, useState } from "react";
import { MessagesSquare } from "lucide-react";

import { useChat } from "@/hooks/use-chat";
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
  const idRef = useRef(0);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView?.({ behavior: "smooth" });
  }, [messages.length, chat.isPending]);

  function nextId() {
    return String((idRef.current += 1));
  }

  function handleSubmit(question: string) {
    setMessages((prev) => [
      ...prev,
      { id: nextId(), role: "user", content: question },
    ]);

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
        onError: (error) =>
          setMessages((prev) => [
            ...prev,
            {
              id: nextId(),
              role: "assistant",
              answer:
                error.message || "The request failed. Please try again.",
              citations: [],
              isError: true,
            },
          ]),
      },
    );
  }

  const isEmpty = messages.length === 0 && !chat.isPending;

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
                  className="rounded-full border border-border bg-card px-3 py-1.5 text-xs text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
                >
                  {suggestion}
                </button>
              ))}
            </div>
          </div>
        ) : (
          <div className="space-y-4 py-1">
            {messages.map((message) => (
              <ChatMessageItem key={message.id} message={message} />
            ))}
            {chat.isPending && <ChatThinking />}
            <div ref={bottomRef} />
          </div>
        )}
      </div>

      <ChatComposer onSubmit={handleSubmit} pending={chat.isPending} />
    </div>
  );
}
