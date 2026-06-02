import { AlertTriangle } from "lucide-react";

import { cn } from "@/lib/utils";
import { CitationCard } from "@/components/repo/chat/citation-card";
import type { ChatMessage } from "@/components/repo/chat/types";

/** A single chat turn: a user prompt or an assistant answer with citations. */
export function ChatMessageItem({ message }: { message: ChatMessage }) {
  if (message.role === "user") {
    return (
      <div className="flex justify-end">
        <div className="max-w-[80%] whitespace-pre-wrap rounded-2xl rounded-br-sm bg-primary px-4 py-2.5 text-sm text-primary-foreground">
          {message.content}
        </div>
      </div>
    );
  }

  return (
    <div className="flex justify-start">
      <div className="max-w-[80%] space-y-3">
        <div
          className={cn(
            "rounded-2xl rounded-bl-sm border px-4 py-2.5 text-sm",
            message.isError
              ? "border-destructive/40 bg-destructive/10 text-foreground"
              : "border-border bg-card text-foreground",
          )}
        >
          {message.isError && (
            <span className="mb-1 flex items-center gap-1.5 text-xs font-medium text-destructive">
              <AlertTriangle className="size-3.5" />
              Something went wrong
            </span>
          )}
          <p className="whitespace-pre-wrap leading-relaxed">{message.answer}</p>
        </div>

        {message.citations.length > 0 && (
          <div className="space-y-1.5">
            <p className="px-1 text-xs font-medium text-muted-foreground">
              {message.citations.length} citation
              {message.citations.length === 1 ? "" : "s"}
            </p>
            {message.citations.map((citation, i) => (
              <CitationCard
                key={`${citation.file_path}:${citation.start_line}-${i}`}
                citation={citation}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
