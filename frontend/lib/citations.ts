import type { CitationResponse } from "@/lib/api/types";

/**
 * Format a citation's source location as `file_path:start-end` (relative path
 * as returned by the backend). Collapses to `file_path:line` when the range is
 * a single line. Pure — safe to unit test.
 */
export function formatCitationRange(citation: CitationResponse): string {
  const { file_path, start_line, end_line } = citation;
  const lines =
    start_line === end_line ? `${start_line}` : `${start_line}-${end_line}`;
  return `${file_path}:${lines}`;
}
