"use client";

import { useEffect, useRef, useState } from "react";
import { KeyRound } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

interface AccessCodeModalProps {
  open: boolean;
  /** Called with the trimmed code when the user submits. */
  onSubmit: (code: string) => void;
  /** Called on Escape / overlay click / cancel. */
  onClose: () => void;
  /** Inline error (e.g. "Invalid access code") shown above the input. */
  error?: string | null;
}

/**
 * Lightweight access-code prompt. Hand-rolled (no Dialog dependency) using the
 * Indigo Slate tokens. This is a UX friction-reducer — the gate is enforced
 * server-side regardless of what happens here.
 */
export function AccessCodeModal({
  open,
  onSubmit,
  onClose,
  error,
}: AccessCodeModalProps) {
  const [value, setValue] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);

  // Reset the field and focus the input whenever the modal opens.
  useEffect(() => {
    if (open) {
      setValue("");
      inputRef.current?.focus();
    }
  }, [open]);

  // Close on Escape while open.
  useEffect(() => {
    if (!open) return;
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") onClose();
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [open, onClose]);

  if (!open) return null;

  function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const trimmed = value.trim();
    if (!trimmed) return;
    onSubmit(trimmed);
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-background/80 p-4 backdrop-blur-sm"
      onMouseDown={onClose}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="access-code-title"
        className="w-full max-w-sm rounded-lg border border-border bg-card p-6 shadow-lg"
        onMouseDown={(event) => event.stopPropagation()}
      >
        <div className="flex items-center gap-3">
          <span className="flex size-9 items-center justify-center rounded-md bg-secondary text-primary">
            <KeyRound className="size-4" />
          </span>
          <h2
            id="access-code-title"
            className="text-base font-semibold text-foreground"
          >
            Enter access code
          </h2>
        </div>

        <p className="mt-3 text-sm text-muted-foreground">
          This demo is rate-limited to control API costs. Enter the access code
          to try it live.
        </p>

        <form onSubmit={handleSubmit} className="mt-4 flex flex-col gap-3">
          {error ? (
            <p className="text-sm text-destructive" role="alert">
              {error}
            </p>
          ) : null}
          <Input
            ref={inputRef}
            type="text"
            autoComplete="off"
            autoCapitalize="none"
            spellCheck={false}
            value={value}
            onChange={(event) => setValue(event.target.value)}
            placeholder="Access code"
            aria-label="Access code"
            className="h-10 font-mono text-sm"
          />
          <div className="flex justify-end gap-2">
            <Button type="button" variant="ghost" onClick={onClose}>
              Cancel
            </Button>
            <Button type="submit" disabled={!value.trim()}>
              Continue
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}
