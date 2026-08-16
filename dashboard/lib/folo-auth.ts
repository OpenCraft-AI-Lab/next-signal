/**
 * Browser sign-in for the Folo credential.
 *
 * No `server-only` import, deliberately: it cannot resolve under the node test
 * runner, and this module carries tests. That matches the other tested
 * server-side modules here (`lib/goals.ts`, `lib/wiki.ts`). Nothing at module
 * scope holds a secret, and only route handlers import it.
 *
 * Folo issues no API token: `FOLO_TOKEN` is a better-auth *session* value, so
 * without this flow the only ways to obtain one are copying a browser cookie or
 * reading `~/.folo/config.json` after a local `folocli login` — the hand
 * extraction this whole change exists to remove.
 *
 * ## Why the dashboard hosts the callback instead of running `folocli login`
 *
 * `folocli login` serves its own callback on `127.0.0.1` at an *ephemeral* port
 * and hands Folo a `cli_callback` pointing there. In the container deployment
 * that address resolves to the host in the operator's browser, not to the
 * container, and the port cannot be published because it is chosen at runtime.
 * The dashboard, by contrast, is already published on the host loopback at a
 * known port — so it is the one process in the stack a browser can reach.
 *
 * ## The handshake
 *
 *   1. open `<web>/login?cli_callback=<our callback>`
 *   2. Folo redirects the browser to `<our callback>?token=<one-time token>`
 *   3. POST that token to `<api>/better-auth/one-time-token/apply`
 *      (falling back to `/verify` on 404, as folocli does)
 *   4. read the session token from `Set-Cookie` or the response body
 *
 * Steps 1 and 3 are folocli's private arrangement with Folo's web app —
 * undocumented and unversioned. It is the same class of dependency as pinning
 * `folocli@0.0.5` and parsing its private JSON envelopes, and it is contained
 * here: if Folo changes the contract, this module is the only thing to fix, and
 * manual entry keeps working meanwhile.
 *
 * No token — one-time or session — is ever returned to the client or logged.
 */

/** Production Folo only. A dev/staging switch would be configuration nobody here uses. */
const FOLO_API_ROOT = "https://api.folo.is";
const FOLO_WEB_ROOT = "https://app.folo.is";

const APPLY_PATH = "/better-auth/one-time-token/apply";
const VERIFY_PATH = "/better-auth/one-time-token/verify";

/** The only host a sign-in may navigate to. */
const ALLOWED_SIGN_IN_HOSTS = new Set(["app.folo.is"]);

/** Long enough to sign in, short enough that a stale attempt cannot linger. */
export const SIGN_IN_TIMEOUT_MS = 5 * 60_000;

/** Cleared this long after finishing, so the UI can still read the outcome. */
const FINISHED_TTL_MS = 60_000;

const EXCHANGE_TIMEOUT_MS = 15_000;

export type FoloSignInPhase =
  | "running"
  | "connected"
  | "failed"
  | "cancelled"
  | "timed_out";

/** What the client is allowed to see. Deliberately carries no token. */
export interface FoloSignInSession {
  id: string;
  phase: FoloSignInPhase;
  signInUrl: string | null;
  error: string | null;
  startedAt: string;
  finishedAt: string | null;
}

interface ManagedSession extends FoloSignInSession {
  timer: ReturnType<typeof setTimeout> | null;
}

type Registry = { current: ManagedSession | null };

function registry(): Registry {
  const root = globalThis as typeof globalThis & { nsFoloAuth?: Registry };
  if (!root.nsFoloAuth) root.nsFoloAuth = { current: null };
  return root.nsFoloAuth;
}

function snapshot(session: ManagedSession): FoloSignInSession {
  const { timer: _timer, ...view } = session;
  return { ...view };
}

/** Strip newlines and cap length: an upstream message is not ours to trust. */
function safeMessage(value: unknown): string {
  const message = value instanceof Error ? value.message : String(value);
  return message.replace(/[\r\n\t]+/g, " ").slice(0, 300);
}

/**
 * The URL the operator's browser is sent to, carrying the address Folo should
 * hand the one-time token back to.
 */
export function foloSignInUrl(callbackUrl: string): string {
  const callback = new URL(callbackUrl); // throws on a malformed callback
  if (callback.protocol !== "http:" && callback.protocol !== "https:") {
    throw new Error(`callback must be an http(s) URL: ${callbackUrl}`);
  }
  const url = new URL(FOLO_WEB_ROOT);
  url.pathname = "/login";
  url.searchParams.set("cli_callback", callback.toString());
  return url.toString();
}

/**
 * Whether a URL may be offered to the operator as a navigation target.
 * Fails closed: anything not HTTPS on the exact Folo sign-in host is rejected,
 * so a redirect or a changed constant cannot turn this into an open redirector.
 */
export function isAllowedFoloSignInUrl(value: string): boolean {
  let url: URL;
  try {
    url = new URL(value);
  } catch {
    return false;
  }
  return url.protocol === "https:" && ALLOWED_SIGN_IN_HOSTS.has(url.hostname);
}

/** Pull the session token out of a `Set-Cookie`, matching folocli's own rule. */
function sessionTokenFromCookies(response: Response): string | undefined {
  const values =
    typeof response.headers.getSetCookie === "function"
      ? response.headers.getSetCookie()
      : [response.headers.get("set-cookie") ?? ""];
  for (const value of values) {
    const match = value.match(/(?:__Secure-)?better-auth\.session_token=([^;]+)/);
    if (match?.[1]) return match[1];
  }
  return undefined;
}

function sessionTokenFromBody(data: unknown): string | undefined {
  if (!data || typeof data !== "object") return undefined;
  const session = (data as { session?: unknown }).session;
  if (session && typeof session === "object") {
    const token = (session as { token?: unknown }).token;
    if (typeof token === "string" && token) return token;
  }
  return undefined;
}

async function postToken(
  url: string,
  oneTimeToken: string,
  fetchImpl: typeof fetch,
): Promise<Response> {
  return fetchImpl(url, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ token: oneTimeToken }),
    signal: AbortSignal.timeout(EXCHANGE_TIMEOUT_MS),
  });
}

/**
 * Trade the one-time token from the callback for a durable session token.
 *
 * `/apply` first and `/verify` only on 404, mirroring folocli so both server
 * versions work. Errors never carry either token: the message names the step.
 */
export async function exchangeOneTimeToken(
  oneTimeToken: string,
  fetchImpl: typeof fetch = fetch,
): Promise<string> {
  if (!oneTimeToken.trim()) throw new Error("Folo returned no sign-in token");

  let response: Response;
  try {
    response = await postToken(
      `${FOLO_API_ROOT}${APPLY_PATH}`,
      oneTimeToken,
      fetchImpl,
    );
  } catch (err) {
    throw new Error(`Could not reach Folo to complete sign-in: ${safeMessage(err)}`);
  }

  if (response.status === 404) {
    try {
      response = await postToken(
        `${FOLO_API_ROOT}${VERIFY_PATH}`,
        oneTimeToken,
        fetchImpl,
      );
    } catch (err) {
      throw new Error(
        `Could not reach Folo to complete sign-in: ${safeMessage(err)}`,
      );
    }
  }

  if (!response.ok) {
    throw new Error(`Folo rejected the sign-in token (HTTP ${response.status})`);
  }

  const body = await response.json().catch(() => null);
  const token = sessionTokenFromCookies(response) ?? sessionTokenFromBody(body);
  if (!token) {
    throw new Error("Folo accepted the sign-in but returned no session token");
  }
  return token;
}

// ---------------------------------------------------------------------------
// One in-flight attempt, held in memory
// ---------------------------------------------------------------------------

export function getFoloSignIn(): FoloSignInSession | null {
  const session = registry().current;
  return session ? snapshot(session) : null;
}

function finish(
  session: ManagedSession,
  phase: Exclude<FoloSignInPhase, "running">,
  error: string | null,
): void {
  if (session.phase !== "running") return;
  if (session.timer) clearTimeout(session.timer);
  session.phase = phase;
  session.error = error;
  session.finishedAt = new Date().toISOString();
  setTimeout(() => {
    if (registry().current === session) registry().current = null;
  }, FINISHED_TTL_MS).unref?.();
}

/**
 * Begin a sign-in. One at a time: a second attempt would race two callbacks
 * onto one credential, and the last writer would win silently.
 */
export function startFoloSignIn(callbackUrl: string): FoloSignInSession {
  const existing = registry().current;
  if (existing?.phase === "running") {
    throw new Error("A Folo sign-in is already running");
  }

  const signInUrl = foloSignInUrl(callbackUrl);
  if (!isAllowedFoloSignInUrl(signInUrl)) {
    // Unreachable while the constants hold; kept so a future edit to them
    // cannot quietly produce a URL the UI would navigate to.
    throw new Error("Refusing to offer a sign-in URL outside Folo");
  }

  const session: ManagedSession = {
    id: crypto.randomUUID(),
    phase: "running",
    signInUrl,
    error: null,
    startedAt: new Date().toISOString(),
    finishedAt: null,
    timer: null,
  };
  session.timer = setTimeout(
    () => finish(session, "timed_out", "Sign-in timed out"),
    SIGN_IN_TIMEOUT_MS,
  );
  session.timer.unref?.();
  registry().current = session;
  return snapshot(session);
}

export function cancelFoloSignIn(): FoloSignInSession {
  const session = registry().current;
  if (!session || session.phase !== "running") {
    throw new Error("No Folo sign-in is running");
  }
  finish(session, "cancelled", null);
  return snapshot(session);
}

/** Mark the running attempt finished. No-op when nothing is running. */
export function completeFoloSignIn(): void {
  const session = registry().current;
  if (session) finish(session, "connected", null);
}

export function failFoloSignIn(error: string): void {
  const session = registry().current;
  if (session) finish(session, "failed", safeMessage(error));
}
