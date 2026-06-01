import { ArrowRight, GitBranch, MessagesSquare, Network } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

const benefits = [
  {
    icon: MessagesSquare,
    title: "Chat with the code",
    body: "Ask questions and get grounded answers with citations to real files and line ranges.",
  },
  {
    icon: Network,
    title: "See the dependencies",
    body: "An interactive graph of how files import one another, with danger-zone analysis.",
  },
  {
    icon: GitBranch,
    title: "Onboard in minutes",
    body: "Paste a public GitHub URL — we index it with AST parsing so you skip the cold start.",
  },
];

export default function Home() {
  return (
    <div className="container flex flex-col items-center px-6 py-24 text-center sm:py-32">
      <span className="mb-5 inline-flex items-center rounded-full border border-border bg-card px-3 py-1 text-xs font-medium text-muted-foreground">
        AI codebase onboarding
      </span>

      <h1 className="max-w-3xl text-balance text-4xl font-semibold tracking-tight sm:text-5xl md:text-6xl">
        Understand any codebase{" "}
        <span className="text-primary">in minutes</span>
      </h1>

      <p className="mt-5 max-w-xl text-pretty text-base text-muted-foreground sm:text-lg">
        Paste a public GitHub URL. ContextCode indexes it, lets you chat with it
        via RAG, and maps its dependency graph.
      </p>

      {/* Stub — submission wiring lands in a later step. */}
      <form className="mt-8 flex w-full max-w-md flex-col gap-3 sm:flex-row">
        <Input
          type="url"
          placeholder="https://github.com/owner/repo"
          aria-label="Public GitHub repository URL"
          className="h-11 font-mono text-sm"
          disabled
        />
        <Button type="submit" size="lg" className="h-11 gap-2" disabled>
          Index repo
          <ArrowRight className="size-4" />
        </Button>
      </form>

      <div className="mt-20 grid w-full max-w-4xl gap-6 text-left sm:grid-cols-3">
        {benefits.map(({ icon: Icon, title, body }) => (
          <div
            key={title}
            className="rounded-lg border border-border bg-card p-5"
          >
            <Icon className="size-5 text-primary" />
            <h2 className="mt-3 text-sm font-semibold">{title}</h2>
            <p className="mt-1.5 text-sm text-muted-foreground">{body}</p>
          </div>
        ))}
      </div>
    </div>
  );
}
