import { describe, expect, it } from "vitest";

import type { CitationResponse } from "@/lib/api/types";
import { formatCitationRange } from "@/lib/citations";

function citation(over: Partial<CitationResponse> = {}): CitationResponse {
  return {
    file_path: "app/services/rag.py",
    function_name: "build_context",
    start_line: 10,
    end_line: 42,
    chunk_type: "function",
    snippet: "def build_context(...):\n    ...",
    ...over,
  };
}

describe("formatCitationRange", () => {
  it("renders a multi-line range as file:start-end", () => {
    expect(formatCitationRange(citation())).toBe("app/services/rag.py:10-42");
  });

  it("collapses a single-line range to file:line", () => {
    expect(
      formatCitationRange(citation({ start_line: 7, end_line: 7 })),
    ).toBe("app/services/rag.py:7");
  });

  it("preserves the relative path verbatim", () => {
    expect(
      formatCitationRange(
        citation({ file_path: "src/index.ts", start_line: 1, end_line: 3 }),
      ),
    ).toBe("src/index.ts:1-3");
  });
});
