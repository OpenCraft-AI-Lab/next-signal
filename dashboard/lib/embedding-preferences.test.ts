import assert from "node:assert/strict";
import test from "node:test";

import {
  embedderIdentity,
  parseEmbeddingPreferences,
  serializeEmbeddingPreferences,
  validateEmbeddingPreferences,
  type EmbeddingPreferences,
} from "./embedding-preferences";

/** Stands in for what `configs/models.yaml::embedders` resolves to. */
const BASE: EmbeddingPreferences = {
  provider: "omlx",
  omlx: { model: "Qwen3-Embedding-0.6B-8bit" },
  openai: { model: "text-embedding-3-small" },
  openaiCompatible: null,
};

const COMPATIBLE = {
  base_url: "https://host.example/v1",
  model: "bge-m3",
  api_key_env: "MY_EMBED_KEY",
  space_id: "house-bge-m3",
};

test("an absent file keeps the configured baseline", () => {
  assert.deepEqual(parseEmbeddingPreferences("{}", BASE), BASE);
});

test("a partial section inherits its baseline model", () => {
  assert.deepEqual(
    parseEmbeddingPreferences(JSON.stringify({ provider: "openai" }), BASE),
    { ...BASE, provider: "openai" },
  );
});

test("a complete compatible section round-trips", () => {
  const parsed = parseEmbeddingPreferences(
    JSON.stringify({ provider: "openai_compatible", openai_compatible: COMPATIBLE }),
    BASE,
  );
  assert.deepEqual(parsed.openaiCompatible, {
    baseUrl: "https://host.example/v1",
    model: "bge-m3",
    apiKeyEnv: "MY_EMBED_KEY",
    spaceId: "house-bge-m3",
  });
  assert.equal(embedderIdentity(parsed), "openai_compatible:house-bge-m3");
});

test("a trailing slash is normalized away before the route is appended", () => {
  const parsed = parseEmbeddingPreferences(
    JSON.stringify({
      openai_compatible: { ...COMPATIBLE, base_url: "https://host.example/v1//" },
    }),
    BASE,
  );
  assert.equal(parsed.openaiCompatible?.baseUrl, "https://host.example/v1");
});

test("serialization writes the variable name and no credential", () => {
  const written = JSON.parse(
    serializeEmbeddingPreferences({
      ...BASE,
      provider: "openai_compatible",
      openaiCompatible: {
        baseUrl: "https://host.example/v1",
        model: "bge-m3",
        apiKeyEnv: "MY_EMBED_KEY",
        spaceId: "house-bge-m3",
      },
    }),
  );
  assert.deepEqual(Object.keys(written.openai_compatible).sort(), [
    "api_key_env",
    "base_url",
    "model",
    "space_id",
  ]);
  assert.equal(written.openai_compatible.api_key_env, "MY_EMBED_KEY");
  assert.equal(written.updated_by, "dashboard");
});

test("an unconfigured compatible section is omitted rather than stubbed", () => {
  const written = JSON.parse(serializeEmbeddingPreferences(BASE));
  assert.equal("openai_compatible" in written, false);
});

for (const [name, payload] of [
  ["unknown top-level key", { temperature: 0.4 }],
  ["unknown section key", { omlx: { dim: 512 } }],
  ["unknown provider", { provider: "ollama" }],
  ["invalid model id", { omlx: { model: "has spaces" } }],
  ["compatible selected with no section", { provider: "openai_compatible" }],
  ["partial compatible section", { openai_compatible: { base_url: "https://h.example/v1" } }],
  ["lowercase key variable", { openai_compatible: { ...COMPATIBLE, api_key_env: "lower" } }],
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
] as const) {
  test(`rejects ${name}`, () => {
    assert.throws(() => parseEmbeddingPreferences(JSON.stringify(payload), BASE));
  });
}

test("rejects an invalid selection on write, not only on read", () => {
  assert.throws(() =>
    validateEmbeddingPreferences({ ...BASE, provider: "openai_compatible" }),
  );
});
