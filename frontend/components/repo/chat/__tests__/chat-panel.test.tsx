import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ChatPanel } from "@/components/repo/chat/chat-panel";
import { ApiError } from "@/lib/api/client";
import { postChat } from "@/lib/api/chat";
import {
  GLOBAL_LIMIT_MESSAGE,
  SESSION_LIMIT_MESSAGE,
} from "@/lib/demo-session";
import type { ChatResponse } from "@/lib/api/types";

vi.mock("@/lib/api/chat", () => ({ postChat: vi.fn() }));

// Demo-session hook is mocked: minting (Turnstile + POST /demo/session) is
// exercised in its own unit; here we only need the chat orchestration.
const { ensureSession, refreshSession, clearSession } = vi.hoisted(() => ({
  ensureSession: vi.fn(),
  refreshSession: vi.fn(),
  clearSession: vi.fn(),
}));

vi.mock("@/hooks/use-demo-session", () => ({
  useDemoSession: () => ({
    sessionId: "session-1",
    ensureSession,
    refreshSession,
    clearSession,
  }),
}));

const mockedPostChat = vi.mocked(postChat);

function renderPanel() {
  const client = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });
  return render(
    <QueryClientProvider client={client}>
      <ChatPanel repoId="repo-1" />
    </QueryClientProvider>,
  );
}

function ask(question: string) {
  const textarea = screen.getByLabelText(/ask a question/i);
  fireEvent.change(textarea, { target: { value: question } });
  fireEvent.keyDown(textarea, { key: "Enter" });
}

beforeEach(() => {
  ensureSession.mockResolvedValue("session-1");
  refreshSession.mockResolvedValue("session-2");
});

afterEach(() => {
  vi.clearAllMocks();
});

describe("ChatPanel", () => {
  it("renders the user message, then the answer with a citation", async () => {
    const response: ChatResponse = {
      answer: "It is a RAG service.",
      citations: [
        {
          file_path: "app/rag.py",
          function_name: "run",
          start_line: 5,
          end_line: 9,
          chunk_type: "function",
          snippet: "def run(): ...",
        },
      ],
    };
    mockedPostChat.mockResolvedValueOnce(response);

    renderPanel();
    ask("What is this?");

    expect(screen.getByText("What is this?")).toBeInTheDocument();
    expect(await screen.findByText("It is a RAG service.")).toBeInTheDocument();
    expect(screen.getByText("app/rag.py:5-9")).toBeInTheDocument();
    expect(screen.getByText("function")).toBeInTheDocument();
    // A demo session was ensured before the request fired.
    expect(ensureSession).toHaveBeenCalledTimes(1);
  });

  it("renders an answer with no citation block when citations are empty", async () => {
    mockedPostChat.mockResolvedValueOnce({
      answer: "I can only answer questions about this repo.",
      citations: [],
    });

    renderPanel();
    ask("What's the weather?");

    expect(
      await screen.findByText(/only answer questions/i),
    ).toBeInTheDocument();
    expect(screen.queryByText(/citation/i)).not.toBeInTheDocument();
  });

  it("shows an animated thinking indicator while pending, then clears it", async () => {
    let resolve!: (value: ChatResponse) => void;
    mockedPostChat.mockReturnValueOnce(
      new Promise<ChatResponse>((r) => {
        resolve = r;
      }),
    );

    renderPanel();
    ask("hello");

    expect(await screen.findByLabelText(/thinking/i)).toBeInTheDocument();

    resolve({ answer: "Hi there.", citations: [] });

    expect(await screen.findByText("Hi there.")).toBeInTheDocument();
    expect(screen.queryByLabelText(/thinking/i)).not.toBeInTheDocument();
  });

  it("renders an error bubble when the request fails", async () => {
    mockedPostChat.mockRejectedValueOnce(new Error("Network down"));

    renderPanel();
    ask("hi");

    expect(await screen.findByText("Network down")).toBeInTheDocument();
    expect(screen.getByText(/something went wrong/i)).toBeInTheDocument();
  });

  it("re-mints the session and retries once on a 401", async () => {
    mockedPostChat
      .mockRejectedValueOnce(
        new ApiError(401, "Unauthorized", {
          detail: "Missing or invalid demo session",
        }),
      )
      .mockResolvedValueOnce({ answer: "Recovered answer.", citations: [] });

    renderPanel();
    ask("hi");

    expect(await screen.findByText("Recovered answer.")).toBeInTheDocument();
    expect(clearSession).toHaveBeenCalledTimes(1);
    expect(refreshSession).toHaveBeenCalledTimes(1);
    expect(mockedPostChat).toHaveBeenCalledTimes(2);
  });

  it("shows the per-session message on a session-cap 429", async () => {
    mockedPostChat.mockRejectedValueOnce(
      new ApiError(429, "Too Many Requests", {
        detail: "You've reached the demo message limit for this session.",
      }),
    );

    renderPanel();
    ask("hi");

    expect(await screen.findByText(SESSION_LIMIT_MESSAGE)).toBeInTheDocument();
    expect(refreshSession).not.toHaveBeenCalled();
  });

  it("shows the busy message on a global-cap 429", async () => {
    mockedPostChat.mockRejectedValueOnce(
      new ApiError(429, "Too Many Requests", {
        detail: "Demo is at capacity for today. Please try again tomorrow.",
      }),
    );

    renderPanel();
    ask("hi");

    expect(await screen.findByText(GLOBAL_LIMIT_MESSAGE)).toBeInTheDocument();
  });

  it("shows a verification error when Turnstile minting fails", async () => {
    ensureSession.mockRejectedValueOnce(new Error("Turnstile failed"));

    renderPanel();
    ask("hi");

    expect(
      await screen.findByText(/couldn't verify you're human/i),
    ).toBeInTheDocument();
    expect(mockedPostChat).not.toHaveBeenCalled();
  });
});
