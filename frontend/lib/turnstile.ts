/**
 * Cloudflare Turnstile loader + one-shot challenge runner.
 *
 * The chat gate needs a Turnstile token to mint a demo session. We render a
 * managed/invisible widget (`appearance: "interaction-only"`) on demand: it
 * stays hidden and auto-passes unless Cloudflare decides a human interaction is
 * required, in which case the widget surfaces in a centered overlay so the
 * challenge is usable. The always-pass test site key
 * `1x00000000000000000000AA` resolves immediately, which is what local dev and
 * the E2E suite use.
 */

const SCRIPT_SRC = "https://challenges.cloudflare.com/turnstile/v0/api.js";

/** Reject a stuck challenge rather than hanging the chat flow forever. */
const CHALLENGE_TIMEOUT_MS = 30_000;

interface TurnstileRenderOptions {
  sitekey: string;
  callback: (token: string) => void;
  "error-callback"?: () => void;
  "expired-callback"?: () => void;
  "timeout-callback"?: () => void;
  appearance?: "always" | "execute" | "interaction-only";
  size?: "normal" | "compact" | "flexible" | "invisible";
}

interface TurnstileApi {
  ready: (cb: () => void) => void;
  render: (
    container: HTMLElement | string,
    options: TurnstileRenderOptions,
  ) => string;
  remove: (widgetId: string) => void;
  reset: (widgetId: string) => void;
}

declare global {
  interface Window {
    turnstile?: TurnstileApi;
  }
}

let scriptPromise: Promise<void> | null = null;

/** Inject the Turnstile script once and resolve when `window.turnstile` is ready. */
function loadTurnstileScript(): Promise<void> {
  if (typeof window === "undefined") {
    return Promise.reject(new Error("Turnstile is only available in the browser"));
  }
  if (window.turnstile) return Promise.resolve();
  if (scriptPromise) return scriptPromise;

  scriptPromise = new Promise<void>((resolve, reject) => {
    const script = document.createElement("script");
    script.src = SCRIPT_SRC;
    script.async = true;
    script.defer = true;
    script.onload = () => resolve();
    script.onerror = () => {
      scriptPromise = null; // allow a later retry
      reject(new Error("Failed to load the Turnstile script"));
    };
    document.head.appendChild(script);
  });
  return scriptPromise;
}

/**
 * Run a single Turnstile challenge and resolve with the response token.
 * Renders into a transient centered container that is removed once a verdict
 * (token, error, expiry, or timeout) arrives.
 */
export async function executeTurnstile(siteKey: string): Promise<string> {
  await loadTurnstileScript();
  const turnstile = window.turnstile;
  if (!turnstile) {
    throw new Error("Turnstile failed to initialize");
  }

  return new Promise<string>((resolve, reject) => {
    turnstile.ready(() => {
      const container = document.createElement("div");
      // Centered + high z-index so an interactive challenge (rare; never with
      // the test key) is visible and usable. Hidden otherwise.
      container.style.position = "fixed";
      container.style.top = "50%";
      container.style.left = "50%";
      container.style.transform = "translate(-50%, -50%)";
      container.style.zIndex = "100";
      document.body.appendChild(container);

      let widgetId: string | undefined;
      let settled = false;

      const cleanup = () => {
        clearTimeout(timer);
        try {
          if (widgetId) turnstile.remove(widgetId);
        } catch {
          // widget may already be gone — ignore
        }
        container.remove();
      };

      const succeed = (token: string) => {
        if (settled) return;
        settled = true;
        cleanup();
        resolve(token);
      };

      const fail = (message: string) => {
        if (settled) return;
        settled = true;
        cleanup();
        reject(new Error(message));
      };

      const timer = setTimeout(
        () => fail("Turnstile challenge timed out"),
        CHALLENGE_TIMEOUT_MS,
      );

      try {
        widgetId = turnstile.render(container, {
          sitekey: siteKey,
          appearance: "interaction-only",
          callback: (token) => succeed(token),
          "error-callback": () => fail("Turnstile challenge failed"),
          "expired-callback": () => fail("Turnstile token expired"),
          "timeout-callback": () => fail("Turnstile challenge timed out"),
        });
      } catch (err) {
        fail(err instanceof Error ? err.message : "Turnstile render failed");
      }
    });
  });
}
