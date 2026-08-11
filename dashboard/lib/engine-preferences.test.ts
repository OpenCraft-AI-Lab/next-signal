import assert from "node:assert/strict";
import test from "node:test";

import {
  parseEnginePreferences,
  serializeEnginePreferences,
  validateEnginePreferences,
  type EnginePreferences,
} from "./engine-preferences";

/** Stands in for what `configs/models.yaml` + the environment resolve to. */
const BASE: EnginePreferences = {
  primary: "omlx",
  fallback: "deepseek",
  omlx: {
    baseUrl: "http://host.docker.internal:8000/v1",
    model: "Qwen3.5-122B-A10B-mlx-oQ4",
    parallel: 2,
  },
  deepseek: { model: "deepseek-v4-flash", reasoning: "low" },
};

test("parses a fully specified file", () => {
  assert.deepEqual(
    parseEnginePreferences(
      JSON.stringify({
        primary: "deepseek",
        fallback: "omlx",
        omlx: {
          base_url: "http://127.0.0.1:9000/v1",
          model: "Qwen3-8B",
          parallel: 1,
        },
        deepseek: { model: "deepseek-v4", reasoning: "high" },
      }),
      BASE,
    ),
    {
      primary: "deepseek",
      fallback: "omlx",
      omlx: { baseUrl: "http://127.0.0.1:9000/v1", model: "Qwen3-8B", parallel: 1 },
      deepseek: { model: "deepseek-v4", reasoning: "high" },
    },
  );
});

test("absent fields fall back to the configured baseline", () => {
  // A never-touched field must read as what the repo is actually configured
  // with, so a partial file cannot silently rewrite the rest.
  assert.deepEqual(
    parseEnginePreferences(JSON.stringify({ primary: "codex_cli" }), BASE),
    { ...BASE, primary: "codex_cli" },
  );
});

test("an empty file is the baseline", () => {
  assert.deepEqual(parseEnginePreferences("{}", BASE), BASE);
});

test("rejects an engine that falls back to itself", () => {
  assert.throws(
    () => parseEnginePreferences(JSON.stringify({ fallback: "omlx" }), BASE),
    /omlx cannot fall back to itself/,
  );
});

test("`none` is a valid fallback", () => {
  assert.equal(
    parseEnginePreferences(JSON.stringify({ fallback: "none" }), BASE).fallback,
    "none",
  );
});

test("rejects unknown engines, keys, and parallelism", () => {
  assert.throws(
    () => parseEnginePreferences(JSON.stringify({ primary: "ollama" }), BASE),
    /unknown engine: ollama/,
  );
  assert.throws(
    () => parseEnginePreferences(JSON.stringify({ temperature: 0.4 }), BASE),
    /unknown engine preference: temperature/,
  );
  assert.throws(
    () => parseEnginePreferences(JSON.stringify({ omlx: { parallel: 3 } }), BASE),
    /unsupported OMLX parallelism: 3/,
  );
});

test("rejects an endpoint with no scheme", () => {
  // A bare host is accepted by the OpenAI client and then 404s at call time,
  // which is much harder to diagnose than a rejected save.
  assert.throws(
    () =>
      parseEnginePreferences(
        JSON.stringify({ omlx: { base_url: "host.docker.internal:8000/v1" } }),
        BASE,
      ),
    /must be an http\(s\) URL/,
  );
});

test("trims before validating and storing", () => {
  const stored = JSON.parse(
    serializeEnginePreferences({
      ...BASE,
      omlx: { ...BASE.omlx, model: "  Qwen3-8B  " },
    }),
  );
  assert.equal(stored.omlx.model, "Qwen3-8B");
});

test("serializes snake_case and stamps provenance", () => {
  const stored = JSON.parse(serializeEnginePreferences(BASE));
  assert.deepEqual(stored.omlx, {
    base_url: BASE.omlx.baseUrl,
    model: BASE.omlx.model,
    parallel: 2,
  });
  assert.equal(stored.updated_by, "dashboard");
  assert.equal(typeof stored.updated_at, "string");
});

test("round-trips through the parser", () => {
  const next: EnginePreferences = {
    ...BASE,
    primary: "claude_cli",
    fallback: "none",
  };
  assert.deepEqual(parseEnginePreferences(serializeEnginePreferences(next), BASE), next);
});

test("validate rejects a blank model outright", () => {
  assert.throws(
    () =>
      validateEnginePreferences({
        ...BASE,
        deepseek: { ...BASE.deepseek, model: "  " },
      }),
    /invalid DeepSeek model identifier/,
  );
});
