import { saveCredential } from "@/lib/actions/secrets";
import {
  completeFoloSignIn,
  exchangeOneTimeToken,
  failFoloSignIn,
  getFoloSignIn,
} from "@/lib/folo-auth";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

/**
 * Where Folo sends the operator's browser after they sign in.
 *
 * Reached by a top-level navigation from Folo, so it is deliberately *not*
 * same-origin gated — that check would reject the very redirect it exists to
 * receive. What protects it instead: it only acts when a sign-in this process
 * started is still running, the one-time token is useless without that, and the
 * only thing it can do is write one credential.
 *
 * Responds with a plain page for a human to read and close. Neither the
 * one-time token nor the session token appears in the response or in a log.
 */
function page(title: string, detail: string, status: number): Response {
  const escape = (value: string) =>
    value.replace(/[&<>"]/g, (c) =>
      c === "&" ? "&amp;" : c === "<" ? "&lt;" : c === ">" ? "&gt;" : "&quot;",
    );
  return new Response(
    `<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>${escape(title)}</title>
<style>
  :root { color-scheme: light dark; }
  body { font: 15px/1.6 ui-sans-serif, system-ui, sans-serif; display: grid; place-items: center;
         min-height: 100svh; margin: 0; padding: 24px; text-align: center; }
  h1 { font-size: 17px; margin: 0 0 6px; }
  p { margin: 0; opacity: .7; max-width: 42ch; }
</style>
<div><h1>${escape(title)}</h1><p>${escape(detail)}</p></div>`,
    {
      status,
      headers: {
        "content-type": "text/html; charset=utf-8",
        "Cache-Control": "no-store",
      },
    },
  );
}

export async function GET(request: Request): Promise<Response> {
  const running = getFoloSignIn()?.phase === "running";
  if (!running) {
    // Nothing asked for this: a stale tab, a replayed link, or an attempt that
    // already timed out. Write nothing.
    return page(
      "No sign-in in progress",
      "Start the sign-in again from Settings → Credentials.",
      409,
    );
  }

  const oneTimeToken = new URL(request.url).searchParams.get("token") ?? "";
  if (!oneTimeToken) {
    failFoloSignIn("Folo returned no sign-in token");
    return page(
      "Sign-in failed",
      "Folo did not return a sign-in token. You can paste a token manually in Settings → Credentials.",
      400,
    );
  }

  try {
    const sessionToken = await exchangeOneTimeToken(oneTimeToken);
    await saveCredential("FOLO_TOKEN", sessionToken);
  } catch (error) {
    // The message names the step that failed and never carries either token.
    const message =
      error instanceof Error ? error.message : "Folo sign-in failed";
    failFoloSignIn(message);
    console.error("folo sign-in failed:", message);
    return page(
      "Sign-in failed",
      `${message}. You can paste a token manually in Settings → Credentials.`,
      502,
    );
  }

  completeFoloSignIn();
  return page("Signed in to Folo", "You can close this tab.", 200);
}
