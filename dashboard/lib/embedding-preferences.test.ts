import assert from "node:assert/strict";
import test from "node:test";

import {
  embedderIdentity,
  parseEmbeddingPreferences,
  serializeEmbeddingPreferences,
  validateEmbeddingPreferences,
  type EmbeddingPreferences,
} from "./embedding-preferences";

const OMLX = {
  base_url: "http://127.0.0.1:8081/v1",
  model: "Qwen3-Embedding-0.6B-8bit",
};
const COMPATIBLE = {
  base_url: "https://host.example/v1",
  model: "bge-m3",
  space_id: "house-bge-m3",
};

const UNSELECTED: EmbeddingPreferences = {
  provider: null,
  omlx: null,
  openai: null,
  openaiCompatible: null,
};

test("an empty file selects nothing", () => {
  const parsed = parseEmbeddingPreferences("{}");
  assert.deepEqual(parsed, UNSELECTED);
  assert.equal(embedderIdentity(parsed), null);
});

test("a saved section without a selection stays unselected", () => {
  const parsed = parseEmbeddingPreferences(JSON.stringify({ omlx: OMLX }));
  assert.equal(parsed.provider, null);
  assert.deepEqual(parsed.omlx, {
    baseUrl: "http://127.0.0.1:8081/v1",
    model: "Qwen3-Embedding-0.6B-8bit",
  });
});

test("omlx carries its own endpoint, separate from the engine's", () => {
  const parsed = parseEmbeddingPreferences(
    JSON.stringify({ provider: "omlx", omlx: OMLX }),
  );
  assert.equal(parsed.omlx?.baseUrl, "http://127.0.0.1:8081/v1");
  assert.equal(embedderIdentity(parsed), "omlx:Qwen3-Embedding-0.6B-8bit");
});

test("a complete compatible section round-trips", () => {
  const parsed = parseEmbeddingPreferences(
    JSON.stringify({ provider: "openai_compatible", openai_compatible: COMPATIBLE }),
  );
  assert.deepEqual(parsed.openaiCompatible, {
    baseUrl: "https://host.example/v1",
    model: "bge-m3",
    spaceId: "house-bge-m3",
  });
  assert.equal(embedderIdentity(parsed), "openai_compatible:house-bge-m3");
});

test("a trailing slash is normalized away before the route is appended", () => {
  const parsed = parseEmbeddingPreferences(
    JSON.stringify({
      openai_compatible: { ...COMPATIBLE, base_url: "https://host.example/v1//" },
    }),
  );
  assert.equal(parsed.openaiCompatible?.baseUrl, "https://host.example/v1");
});

test("serialization names no credential at all", () => {
  const written = JSON.parse(
    serializeEmbeddingPreferences({
      ...UNSELECTED,
      provider: "openai_compatible",
      openaiCompatible: {
        baseUrl: "https://host.example/v1",
        model: "bge-m3",
        spaceId: "house-bge-m3",
      },
    }),
  );
  assert.deepEqual(Object.keys(written.openai_compatible).sort(), [
    "base_url",
    "model",
    "space_id",
  ]);
  assert.equal(written.updated_by, "dashboard");
});

test("unconfigured sections are omitted rather than stubbed", () => {
  const written = JSON.parse(serializeEmbeddingPreferences(UNSELECTED));
  assert.equal("provider" in written, false);
  assert.equal("omlx" in written, false);
  assert.equal("openai" in written, false);
  assert.equal("openai_compatible" in written, false);
});

for (const [name, payload] of [
  ["unknown top-level key", { temperature: 0.4 }],
  ["unknown section key", { omlx: { ...OMLX, dim: 512 } }],
  ["unknown provider", { provider: "ollama" }],
  ["invalid model id", { omlx: { ...OMLX, model: "has spaces" } }],
  ["omlx selected with no section", { provider: "omlx" }],
  ["omlx section with no endpoint", { omlx: { model: "bge-m3" } }],
  ["openai selected with no section", { provider: "openai" }],
  ["compatible selected with no section", { provider: "openai_compatible" }],
  ["partial compatible section", { openai_compatible: { base_url: "https://h.example/v1" } }],
  ["a credential name is no longer a field", { openai_compatible: { ...COMPATIBLE, api_key_env: "MY_KEY" } }],
  ["invalid space id", { openai_compatible: { ...COMPATIBLE, space_id: "has spaces" } }],
  ["non-http base URL", { openai_compatible: { ...COMPATIBLE, base_url: "ftp://h.example" } }],
  [
    "credential in userinfo",
    { openai_compatible: { ...COMPATIBLE, base_url: "https://u:p@h.example/v1" } },
  ],
  [
    "credential in query",
    { openai_compatible: { ...COMPATIBLE, base_url: "https://h.example/v1?key=abc" } },
  ],
  [
    "fragment component",
    { openai_compatible: { ...COMPATIBLE, base_url: "https://h.example/v1#k" } },
  ],
  [
    "endpoint rather than API root",
    { openai_compatible: { ...COMPATIBLE, base_url: "https://h.example/v1/embeddings" } },
  ],
  [
    "credential in an omlx URL",
    { omlx: { ...OMLX, base_url: "https://u:p@h.example/v1" } },
  ],
] as const) {
  test(`rejects ${name}`, () => {
    assert.throws(() => parseEmbeddingPreferences(JSON.stringify(payload)));
  });
}

test("rejects an invalid selection on write, not only on read", () => {
  assert.throws(() =>
    validateEmbeddingPreferences({ ...UNSELECTED, provider: "openai_compatible" }),
  );
});
