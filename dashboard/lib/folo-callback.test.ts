import assert from "node:assert/strict";
import { mkdtemp, readdir } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import test from "node:test";

/**
 * The callback route's guard: it is reached by a top-level navigation from
 * Folo, so it cannot be same-origin gated. What stands in for that is the
 * requirement that a sign-in this process started is still running — and the
 * property that matters is that every path which is not a completed exchange
 * writes nothing at all.
 */
async function withRoute<T>(
  body: (
    route: typeof import("../app/api/folo/callback/route"),
    auth: typeof import("./folo-auth"),
    stateDir: string,
  ) => Promise<T>,
): Promise<T> {
  const dir = await mkdtemp(path.join(os.tmpdir(), "ns-folo-cb-"));
  const previous = process.env.NEXT_SIGNAL_STATE_DIR;
  process.env.NEXT_SIGNAL_STATE_DIR = dir;
  (globalThis as { nsFoloAuth?: unknown }).nsFoloAuth = { current: null };
  try {
    const route = (await import(
      `../app/api/folo/callback/route.ts?case=${Math.random()}`
    )) as typeof import("../app/api/folo/callback/route");
    const auth = (await import(
      "./folo-auth"
    )) as typeof import("./folo-auth");
    return await body(route, auth, dir);
  } finally {
    if (previous === undefined) delete process.env.NEXT_SIGNAL_STATE_DIR;
    else process.env.NEXT_SIGNAL_STATE_DIR = previous;
  }
}

const CALLBACK = "http://127.0.0.1:3000/api/folo/callback";

async function storeIsEmpty(stateDir: string): Promise<boolean> {
  const entries = await readdir(stateDir).catch((): string[] => []);
  return !entries.includes("secrets.json");
}

test("a callback with no sign-in running writes nothing", async () => {
  await withRoute(async (route, _auth, stateDir) => {
    const res = await route.GET(new Request(`${CALLBACK}?token=one-time`));

    assert.equal(res.status, 409);
    assert.ok(await storeIsEmpty(stateDir));
  });
});

test("a callback after cancellation writes nothing", async () => {
  await withRoute(async (route, auth, stateDir) => {
    auth.startFoloSignIn(CALLBACK);
    auth.cancelFoloSignIn();

    const res = await route.GET(new Request(`${CALLBACK}?token=one-time`));

    assert.equal(res.status, 409);
    assert.ok(await storeIsEmpty(stateDir));
  });
});

test("a callback with no token fails the attempt and writes nothing", async () => {
  await withRoute(async (route, auth, stateDir) => {
    auth.startFoloSignIn(CALLBACK);

    const res = await route.GET(new Request(CALLBACK));

    assert.equal(res.status, 400);
    assert.equal(auth.getFoloSignIn()?.phase, "failed");
    assert.ok(await storeIsEmpty(stateDir));
  });
});

// No test drives the route with a *valid* token: that path calls Folo, and a
// unit test must not reach a third party. The exchange itself — including that
// neither failure message echoes a token — is covered in `folo-auth.test.ts`
// with an injected fetch, and the end-to-end path is task 9.8 against a real
// account.
