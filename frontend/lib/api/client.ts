/**
 * Typed fetch wrapper for the ContextCode backend.
 *
 * All request/response shapes are sourced from the generated OpenAPI types in
 * `@/types/api` — never hand-written. See lib/api/types.ts for the aliases.
 */

/** Base URL of the FastAPI backend; defaults to local dev. */
export const API_BASE_URL = (
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000"
).replace(/\/+$/, "");

/** Thrown on any non-2xx response. `detail` holds the parsed JSON body. */
export class ApiError extends Error {
  readonly status: number;
  readonly statusText: string;
  readonly detail: unknown;

  constructor(status: number, statusText: string, detail: unknown) {
    super(`API request failed: ${status} ${statusText}`);
    this.name = "ApiError";
    this.status = status;
    this.statusText = statusText;
    this.detail = detail;
  }
}

/**
 * Issue a JSON request against the backend and return the parsed body typed as
 * `T`. Throws {@link ApiError} on any non-2xx response.
 */
export async function apiFetch<T>(
  path: string,
  init?: RequestInit,
): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      Accept: "application/json",
      ...init?.headers,
    },
  });

  if (!response.ok) {
    throw new ApiError(
      response.status,
      response.statusText,
      await safeParseBody(response),
    );
  }

  if (response.status === 204) {
    return undefined as T;
  }

  const text = await response.text();
  return (text ? JSON.parse(text) : undefined) as T;
}

/** Best-effort body parse for error responses — never throws. */
async function safeParseBody(response: Response): Promise<unknown> {
  try {
    const text = await response.text();
    if (!text) return undefined;
    try {
      return JSON.parse(text);
    } catch {
      return text;
    }
  } catch {
    return undefined;
  }
}
