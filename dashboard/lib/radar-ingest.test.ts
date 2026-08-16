import assert from "node:assert/strict";
import { mkdtemp, writeFile } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { test } from "node:test";

import {
  parseFoloEntryEnvelope,
  renderFoloEntryHtml,
  resolveRadarIngestValue,
  type RadarIngestRow,
} from "./radar-ingest";

/**
 * Points `NEXT_SIGNAL_STATE_DIR` at a fresh temp dir and imports a fresh
 * module instance, same pattern as `lib/actions/secrets.test.ts` — so these
 * tests never touch a real `~/.next-signal/secrets.json`.
 */
async function withStore<T>(
  secrets: Record<string, string> | null,
  body: (mod: typeof import("./radar-ingest")) => Promise<T>,
): Promise<T> {
  const dir = await mkdtemp(path.join(os.tmpdir(), "ns-radar-ingest-"));
  if (secrets) {
    await writeFile(
      path.join(dir, "secrets.json"),
      JSON.stringify(secrets),
      "utf-8",
    );
  }
  const previous = process.env.NEXT_SIGNAL_STATE_DIR;
  process.env.NEXT_SIGNAL_STATE_DIR = dir;
  try {
    const mod = (await import(
      `./radar-ingest.ts?case=${Math.random()}`
    )) as typeof import("./radar-ingest");
    return await body(mod);
  } finally {
    if (previous === undefined) delete process.env.NEXT_SIGNAL_STATE_DIR;
    else process.env.NEXT_SIGNAL_STATE_DIR = previous;
  }
}

test("resolveRadarIngestValue stages folo full text before ingest", async () => {
  const row: RadarIngestRow = {
    source: "folo_timeline_articles",
    source_id: "entry-1",
    url: "https://example.com/source",
    title: "Fallback",
  };
  const value = await resolveRadarIngestValue(7, row, {
    fetchFoloEntry: async () => ({
      content: "<p>full text</p>",
      title: "Entry",
    }),
    stageFoloEntry: async (itemId, _row, entry) => {
      assert.equal(itemId, 7);
      assert.equal(entry.title, "Entry");
      return "/tmp/staged.html";
    },
  });
  assert.equal(value, "/tmp/staged.html");
});

test("resolveRadarIngestValue falls back to validated URL for non-folo rows", async () => {
  const value = await resolveRadarIngestValue(
    9,
    {
      source: "hackernews",
      source_id: "x",
      url: "https://example.com/a",
      title: "A",
    },
    {
      fetchFoloEntry: async () => {
        throw new Error("should not fetch");
      },
      stageFoloEntry: async () => {
        throw new Error("should not stage");
      },
    },
  );
  assert.equal(value, "https://example.com/a");
});

test("resolveRadarIngestValue rejects malformed non-folo URL before spawning", async () => {
  await assert.rejects(
    () =>
      resolveRadarIngestValue(
        9,
        { source: "hackernews", source_id: "x", url: "not a url", title: "A" },
        {
          fetchFoloEntry: async () => ({}),
          stageFoloEntry: async () => "/tmp/staged.html",
        },
      ),
    /malformed/,
  );
});

test("folocliEnv rejects before spawning when no token is configured", async () => {
  await withStore(null, async ({ folocliEnv }) => {
    await assert.rejects(() => folocliEnv(), /FOLO_TOKEN is not configured/);
  });
});

test("folocliEnv carries the stored token to the child", async () => {
  await withStore({ FOLO_TOKEN: "test-token" }, async ({ folocliEnv }) => {
    const env = await folocliEnv();
    assert.equal(env.FOLO_TOKEN, "test-token");
  });
});

test("folocliEnv never leaks an unrelated stored credential to folocli", async () => {
  await withStore(
    { FOLO_TOKEN: "test-token", OPENAI_API_KEY: "sk-should-not-leak" },
    async ({ folocliEnv }) => {
      const env = await folocliEnv();
      assert.equal(env.OPENAI_API_KEY, undefined);
    },
  );
});

test("parseFoloEntryEnvelope returns data.entries", () => {
  const entry = parseFoloEntryEnvelope(
    JSON.stringify({ ok: true, data: { entries: { content: "<p>body</p>" } } }),
  );
  assert.equal(entry.content, "<p>body</p>");
});

test("parseFoloEntryEnvelope rejects ok=false", () => {
  assert.throws(
    () =>
      parseFoloEntryEnvelope(
        JSON.stringify({
          ok: false,
          error: { code: "NOT_FOUND", message: "missing" },
        }),
      ),
    /NOT_FOUND/,
  );
});

test("renderFoloEntryHtml preserves source metadata in staged content", () => {
  const html = renderFoloEntryHtml(
    {
      source: "folo",
      source_id: "entry-1",
      url: "https://example.com/source",
      title: "Fallback",
    },
    { title: "Entry", content: "<p>body</p>", author: "Author" },
  );
  assert.match(html, /<title>Entry<\/title>/);
  assert.match(html, /https:\/\/example.com\/source/);
  assert.match(html, /Author/);
  assert.match(html, /<p>body<\/p>/);
});
