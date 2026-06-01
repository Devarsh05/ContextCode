/**
 * Convenience aliases for the generated OpenAPI schemas. These re-export
 * `components["schemas"][...]` from `@/types/api` so callers don't repeat the
 * deep index. Do not hand-write request/response shapes here — regenerate
 * types with `npm run gen:types` when the backend contract changes.
 */
import type { components } from "@/types/api";

export type IndexRequest = components["schemas"]["IndexRequest"];
export type IndexResponse = components["schemas"]["IndexResponse"];

export type ChatRequest = components["schemas"]["ChatRequest"];
export type ChatResponse = components["schemas"]["ChatResponse"];
export type CitationResponse = components["schemas"]["CitationResponse"];

export type GraphResponse = components["schemas"]["GraphResponse"];
export type GraphNodeResponse = components["schemas"]["GraphNodeResponse"];
export type GraphEdgeResponse = components["schemas"]["GraphEdgeResponse"];
