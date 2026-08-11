import assert from "node:assert/strict";
import test from "node:test";

import {
  UNSET_CODING_AGENT_SETTINGS,
  parseCodingAgentSettings,
  serializeCodingAgentSettings,
} from "./coding-agent-preferences";

test("parses configured Codex and Claude defaults", () => {
  assert.deepEqual(
    parseCodingAgentSettings(
      JSON.stringify({
        codex: {
          model: "gpt-5.6-sol",
          model_reasoning_effort: "high",
          service_tier: "fast",
        },
        claude: {
          model: "opus[1m]",
          effort: "xhigh",
        },
      }),
    ),
    {
      codex: {
        model: "gpt-5.6-sol",
        modelReasoningEffort: "high",
        serviceTier: "fast",
      },
      claude: {
        model: "opus[1m]",
        effort: "xhigh",
      },
    },
  );
});

test("unconfigured settings omit both provider sections", () => {
  const payload = JSON.parse(
    serializeCodingAgentSettings(UNSET_CODING_AGENT_SETTINGS),
  );

  assert.equal(payload.codex, undefined);
  assert.equal(payload.claude, undefined);
  assert.equal(payload.updated_by, "dashboard");
  assert.equal(typeof payload.updated_at, "string");
});

test("missing or legacy-empty provider values remain unconfigured", () => {
  assert.deepEqual(parseCodingAgentSettings("{}"), UNSET_CODING_AGENT_SETTINGS);
  assert.deepEqual(
    parseCodingAgentSettings('{"codex":{},"claude":{}}'),
    UNSET_CODING_AGENT_SETTINGS,
  );
});

test("serialization preserves both provider sections", () => {
  const payload = JSON.parse(
    serializeCodingAgentSettings({
      codex: {
        model: "gpt-5.6-sol",
        modelReasoningEffort: "medium",
        serviceTier: "default",
      },
      claude: { model: "sonnet", effort: "max" },
    }),
  );

  assert.deepEqual(payload.codex, {
    model: "gpt-5.6-sol",
    model_reasoning_effort: "medium",
    service_tier: "default",
  });
  assert.deepEqual(payload.claude, { model: "sonnet", effort: "max" });
});

test("rejects invalid provider values and unknown fields", () => {
  for (const raw of [
    '{"codex":{"model":"bad model"}}',
    '{"codex":{"model":""}}',
    '{"codex":{"model_reasoning_effort":"ultra"}}',
    '{"codex":{"service_tier":"priority"}}',
    '{"codex":{"unknown":true}}',
    '{"claude":{"model":"bad model"}}',
    '{"claude":{"model":"sonnet"}}',
    '{"claude":{"effort":"high"}}',
    '{"claude":{"effort":"ultra"}}',
    '{"claude":{"effort":1}}',
    '{"claude":{"unknown":true}}',
    '{"unknown":true}',
  ]) {
    assert.throws(() => parseCodingAgentSettings(raw));
  }
});
