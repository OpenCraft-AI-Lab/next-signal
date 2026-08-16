import assert from "node:assert/strict";
import test from "node:test";

import {
  cancelFoloSignIn,
  exchangeOneTimeToken,
  foloSignInUrl,
  getFoloSignIn,
  isAllowedFoloSignInUrl,
  startFoloSignIn,
} from "./folo-auth";

const CALLBACK = "http://127.0.0.1:3000/api/folo/callback";

/** One in-flight attempt is held on `globalThis`; clear it between tests. */
function reset(): void {
  try {
    cancelFoloSignIn();
  } catch {
    // nothing running
  }
  (globalThis as { nsFoloAuth?: unknown }).nsFoloAuth = { current: null };
}

function response(
  init: {
    status?: number;
    body?: unknown;
    setCookie?: string;
  } = {},
): Response {
  const headers = new Headers({ "content-type": "application/json" });
  if (init.setCookie) headers.append("set-cookie", init.setCookie);
  return new Response(JSON.stringify(init.body ?? {}), {
    status: init.status ?? 200,
    headers,
  });
}

test("the sign-in URL carries our callback to Folo's login page", () => {
  const url = new URL(foloSignInUrl(CALLBACK));

  assert.equal(url.origin, "https://app.folo.is");
  assert.equal(url.pathname, "/login");
  assert.equal(url.searchParams.get("cli_callback"), CALLBACK);
});

test("a malformed callback is rejected rather than sent to Folo", () => {
  assert.throws(() => foloSignInUrl("not a url"));
  assert.throws(() => foloSignInUrl("file:///etc/passwd"), /http\(s\)/);
});

test("only HTTPS Folo hosts may be offered as a navigation target", () => {
  assert.ok(isAllowedFoloSignInUrl("https://app.folo.is/login"));
  assert.ok(!isAllowedFoloSignInUrl("http://app.folo.is/login"));
  assert.ok(!isAllowedFoloSignInUrl("https://app.folo.is.evil.test/login"));
  assert.ok(!isAllowedFoloSignInUrl("https://evil.test/login"));
  assert.ok(!isAllowedFoloSignInUrl("javascript:alert(1)"));
  assert.ok(!isAllowedFoloSignInUrl("garbage"));
});

test("a session token is read from the Set-Cookie header", async () => {
  const token = await exchangeOneTimeToken("one-time", async () =>
    response({ setCookie: "better-auth.session_token=sess-abc; Path=/; HttpOnly" }),
  );

  assert.equal(token, "sess-abc");
});

test("the __Secure- cookie variant is accepted", async () => {
  const token = await exchangeOneTimeToken("one-time", async () =>
    response({ setCookie: "__Secure-better-auth.session_token=sess-xyz; Path=/" }),
  );

  assert.equal(token, "sess-xyz");
});

test("a session token is read from the body when no cookie is set", async () => {
  const token = await exchangeOneTimeToken("one-time", async () =>
    response({ body: { session: { token: "sess-body" } } }),
  );

  assert.equal(token, "sess-body");
});

test("a 404 on apply falls back to verify, as folocli does", async () => {
  const seen: string[] = [];
  const token = await exchangeOneTimeToken("one-time", async (input) => {
    const url = String(input);
    seen.push(new URL(url).pathname);
    return url.endsWith("/apply")
      ? response({ status: 404 })
      : response({ body: { session: { token: "sess-verify" } } });
  });

  assert.equal(token, "sess-verify");
  assert.deepEqual(seen, [
    "/better-auth/one-time-token/apply",
    "/better-auth/one-time-token/verify",
  ]);
});

test("a rejected token fails without echoing it", async () => {
  await assert.rejects(
    () =>
      exchangeOneTimeToken("secret-one-time", async () =>
        response({ status: 401 }),
      ),
    (err: Error) => {
      assert.match(err.message, /HTTP 401/);
      assert.ok(!err.message.includes("secret-one-time"));
      return true;
    },
  );
});

test("a success that returns no token is an error, not an empty credential", async () => {
  await assert.rejects(
    () => exchangeOneTimeToken("one-time", async () => response({ body: {} })),
    /no session token/,
  );
});

test("a transport failure is reported without the token", async () => {
  await assert.rejects(
    () =>
      exchangeOneTimeToken("secret-one-time", async () => {
        throw new Error("ECONNREFUSED");
      }),
    (err: Error) => {
      assert.match(err.message, /Could not reach Folo/);
      assert.ok(!err.message.includes("secret-one-time"));
      return true;
    },
  );
});

test("an empty token never reaches the network", async () => {
  let called = false;
  await assert.rejects(
    () =>
      exchangeOneTimeToken("   ", async () => {
        called = true;
        return response();
      }),
    /no sign-in token/,
  );
  assert.equal(called, false);
});

test("starting a sign-in exposes a URL and no token field", () => {
  reset();
  const session = startFoloSignIn(CALLBACK);

  assert.equal(session.phase, "running");
  assert.ok(isAllowedFoloSignInUrl(session.signInUrl ?? ""));
  assert.deepEqual(Object.keys(session).sort(), [
    "error",
    "finishedAt",
    "id",
    "phase",
    "signInUrl",
    "startedAt",
  ]);
  reset();
});

test("only one sign-in may run at a time", () => {
  reset();
  startFoloSignIn(CALLBACK);

  assert.throws(() => startFoloSignIn(CALLBACK), /already running/);
  reset();
});

test("cancelling ends the attempt and a second cancel is an error", () => {
  reset();
  startFoloSignIn(CALLBACK);

  assert.equal(cancelFoloSignIn().phase, "cancelled");
  assert.equal(getFoloSignIn()?.phase, "cancelled");
  assert.throws(() => cancelFoloSignIn(), /No Folo sign-in is running/);
  reset();
});
