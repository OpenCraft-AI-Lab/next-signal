import assert from "node:assert/strict";
import test from "node:test";

import {
  appendBoundedAuthTranscript,
  isAllowedCodingAgentLoginUrl,
  parseCodingAgentAuthProvider,
} from "./coding-agent-auth-types";

test("provider parsing is an enum, not an executable name", () => {
  assert.equal(parseCodingAgentAuthProvider("codex"), "codex");
  assert.equal(parseCodingAgentAuthProvider("claude"), "claude");
  assert.equal(parseCodingAgentAuthProvider("/bin/sh"), null);
});

test("login URL allowlist requires HTTPS and a real provider domain suffix", () => {
  assert.equal(
    isAllowedCodingAgentLoginUrl(
      "codex",
      "https://auth.openai.com/codex/device",
    ),
    true,
  );
  assert.equal(
    isAllowedCodingAgentLoginUrl(
      "claude",
      "https://claude.com/cai/oauth/authorize",
    ),
    true,
  );
  assert.equal(
    isAllowedCodingAgentLoginUrl(
      "codex",
      "https://openai.com.evil.example/phish",
    ),
    false,
  );
  assert.equal(
    isAllowedCodingAgentLoginUrl("claude", "http://claude.ai/oauth/authorize"),
    false,
  );
  assert.equal(
    isAllowedCodingAgentLoginUrl(
      "claude",
      "https://claude.com.evil.example/cai/oauth/authorize",
    ),
    false,
  );
});

test("authentication transcript keeps only the bounded tail", () => {
  assert.equal(appendBoundedAuthTranscript("1234", "5678", 6), "345678");
});
