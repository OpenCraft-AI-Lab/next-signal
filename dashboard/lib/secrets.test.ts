import assert from "node:assert/strict";
import test from "node:test";

import {
  CREDENTIAL_NAMES,
  assertValidCredentialName,
  credentialPresence,
  isValidCredentialName,
  parseSecrets,
  serializeSecrets,
} from "./secrets";

test("a well-formed store parses to its entries", () => {
  assert.deepEqual(parseSecrets('{"OPENAI_API_KEY":"sk-example"}'), {
    OPENAI_API_KEY: "sk-example",
  });
});

test("an unparseable store is rejected rather than read as empty", () => {
  assert.throws(() => parseSecrets("{ not json"), /invalid credential store/);
});

test("a non-object store is rejected", () => {
  assert.throws(() => parseSecrets('["a"]'), /must be a JSON object/);
});

test("a non-string value is rejected", () => {
  assert.throws(
    () => parseSecrets('{"OPENAI_API_KEY":42}'),
    /OPENAI_API_KEY is number/,
  );
});

test("presence reports every known credential, set or not", () => {
  const presence = credentialPresence({ OPENAI_API_KEY: "sk-example" });

  assert.equal(presence.OPENAI_API_KEY, true);
  assert.equal(presence.FOLO_TOKEN, false);
  assert.deepEqual(Object.keys(presence).sort(), [...CREDENTIAL_NAMES].sort());
});

test("presence never carries a credential value", () => {
  const presence = credentialPresence({ OPENAI_API_KEY: "sk-example" });

  assert.ok(!JSON.stringify(presence).includes("sk-example"));
  for (const value of Object.values(presence)) {
    assert.equal(typeof value, "boolean");
  }
});

test("a whitespace-only value does not count as present", () => {
  assert.equal(credentialPresence({ OPENAI_API_KEY: "   " }).OPENAI_API_KEY, false);
});

test("an operator-defined name is reported when asked for", () => {
  const presence = credentialPresence({ MY_EMBED_KEY: "sk-custom" }, [
    "MY_EMBED_KEY",
  ]);

  assert.equal(presence.MY_EMBED_KEY, true);
});

test("credential names follow the embedding.json pattern", () => {
  assert.ok(isValidCredentialName("MY_EMBED_KEY"));
  assert.ok(!isValidCredentialName("lowercase"));
  assert.ok(!isValidCredentialName("1LEADING_DIGIT"));
  assert.throws(() => assertValidCredentialName("nope"), /credential name/);
});

test("serialization is stable so an unchanged store rewrites identically", () => {
  const once = serializeSecrets({ B_TOKEN: "2", A_TOKEN: "1" });

  assert.equal(once, serializeSecrets({ A_TOKEN: "1", B_TOKEN: "2" }));
  assert.deepEqual(parseSecrets(once), { A_TOKEN: "1", B_TOKEN: "2" });
});
