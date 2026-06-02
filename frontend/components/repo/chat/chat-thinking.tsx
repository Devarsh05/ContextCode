/**
 * Assistant-styled "thinking" bubble: three bouncing dots (not a frozen
 * spinner) shown while a /chat request is in flight.
 */
export function ChatThinking() {
  return (
    <div className="flex justify-start" aria-live="polite" aria-label="Assistant is thinking">
      <div className="flex items-center gap-1.5 rounded-2xl rounded-bl-sm border border-border bg-card px-4 py-3">
        {[0, 150, 300].map((delay) => (
          <span
            key={delay}
            className="size-2 animate-bounce rounded-full bg-muted-foreground/60"
            style={{ animationDelay: `${delay}ms` }}
          />
        ))}
      </div>
    </div>
  );
}
