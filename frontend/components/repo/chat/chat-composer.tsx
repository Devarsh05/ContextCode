"use client";

import { useEffect, useRef, useState } from "react";
import { ArrowUp } from "lucide-react";

import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";

interface ChatComposerProps {
  /** Fired with the trimmed question on submit. */
  onSubmit: (question: string) => void;
  /** Disables input + send while a request is in flight. */
  pending: boolean;
}

const MAX_HEIGHT = 200;

/** Auto-growing chat input. Enter submits; Shift+Enter inserts a newline. */
export function ChatComposer({ onSubmit, pending }: ChatComposerProps) {
  const [value, setValue] = useState("");
  const ref = useRef<HTMLTextAreaElement>(null);

  // Auto-grow to fit content, capped at MAX_HEIGHT.
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, MAX_HEIGHT)}px`;
  }, [value]);

  function submit() {
    const question = value.trim();
    if (!question || pending) return;
    onSubmit(question);
    setValue("");
  }

  function handleKeyDown(event: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      submit();
    }
  }

  const canSend = value.trim().length > 0 && !pending;

  return (
    <div
      className={cn(
        "flex items-end gap-2 rounded-xl border border-input bg-background p-2",
        "focus-within:ring-1 focus-within:ring-ring",
      )}
    >
      <Textarea
        ref={ref}
        rows={1}
        value={value}
        onChange={(e) => setValue(e.target.value)}
        onKeyDown={handleKeyDown}
        disabled={pending}
        placeholder="Ask about this codebase…"
        aria-label="Ask a question about this codebase"
        className="min-h-0 resize-none border-0 bg-transparent px-2 py-1.5 shadow-none focus-visible:ring-0"
      />
      <Button
        type="button"
        size="icon"
        onClick={submit}
        disabled={!canSend}
        aria-label="Send"
        className="size-8 shrink-0 rounded-lg"
      >
        <ArrowUp className="size-4" />
      </Button>
    </div>
  );
}
