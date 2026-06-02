import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ChatPanel } from "@/components/repo/chat/chat-panel";
import { postChat } from "@/lib/api/chat";
import type { ChatResponse } from "@/lib/api/types";

vi.mock("@/lib/api/chat", () => ({ postChat: vi.fn() }));

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
});
